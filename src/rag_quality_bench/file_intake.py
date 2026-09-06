"""Prepare a canonical suite from an explicit, measured local file list."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .intake_io import FileRoot, IntakeError, relative_parts
from .models import BenchmarkSuite, ContractError, Document, MAX_SUITE_BYTES, canonical_sha256

MAX_FILES = 200
MAX_FILE_BYTES = 800_000
MAX_TOTAL_BYTES = 4_000_000
MAX_INTAKE_BYTES = 512_000
SCHEMA = 'rag-lab/file-intake-v1'
FIELDS = {'name','size','sha256','media_type','source_id','title','source_url','license','observed_at','expires_at','trust'}
MEDIA = {'text/plain','text/markdown','application/json'}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise IntakeError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def load_intake(path: str | Path) -> dict[str, Any]:
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_INTAKE_BYTES + 1)
    if len(raw) > MAX_INTAKE_BYTES: raise IntakeError('MANIFEST_BYTE_LIMIT')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(IntakeError('NONFINITE_JSON')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise IntakeError('INVALID_MANIFEST_JSON') from exc
    if not isinstance(value, dict): raise IntakeError('INVALID_MANIFEST')
    return value


def validate_intake(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {'schema_version','files'} or value['schema_version'] != SCHEMA:
        raise IntakeError('INVALID_MANIFEST')
    rows = value['files']
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_FILES:
        raise IntakeError('FILE_COUNT_LIMIT')
    names = set(); ids = set(); total = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise IntakeError('INVALID_ENTRY')
        relative_parts(row['name'])
        # Case-folded names prevent ambiguous Windows aliases; POSIX follows
        # the same portable rule rather than accepting platform-specific inputs.
        key = row['name'].casefold()
        if key in names: raise IntakeError('DUPLICATE_NAME')
        names.add(key)
        if type(row['size']) is not int or not 1 <= row['size'] <= MAX_FILE_BYTES:
            raise IntakeError('INVALID_FILE_SIZE', name=row['name'])
        total += row['size']
        if not isinstance(row['sha256'], str) or re.fullmatch('[0-9a-f]{64}',row['sha256']) is None:
            raise IntakeError('INVALID_SHA256', name=row['name'])
        if not isinstance(row['media_type'],str) or row['media_type'] not in MEDIA: raise IntakeError('UNSUPPORTED_MEDIA', name=row['name'])
        metadata = {k:v for k,v in row.items() if k not in {'name','size','media_type'}}
        try:
            # Validate declared metadata before reading any file bytes.
            document = Document.from_dict({**metadata,'content':'metadata validation placeholder'})
        except (ValueError, TypeError, UnicodeError) as exc:
            raise IntakeError('INVALID_DOCUMENT_METADATA', name=row['name']) from exc
        if document.source_id in ids: raise IntakeError('DUPLICATE_SOURCE_ID')
        ids.add(document.source_id)
    if total > MAX_TOTAL_BYTES: raise IntakeError('TOTAL_BYTE_LIMIT')
    try:
        raw = json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise IntakeError('INVALID_MANIFEST') from exc
    if len(raw) > MAX_INTAKE_BYTES: raise IntakeError('MANIFEST_BYTE_LIMIT')
    # Immutable-by-ownership snapshot; never retain caller-owned dicts/lists.
    clean = json.loads(raw)
    clean['files'].sort(key=lambda row:row['name'])
    return clean


def duplicate_groups(documents):
    exact = {}; normalized = {}
    for document in documents:
        exact.setdefault(document.content, []).append(document.source_id)
        text = re.sub(r'\s+', ' ', document.content.strip().casefold())
        normalized.setdefault(text, []).append(document.source_id)
    def groups(index):
        return sorted(sorted(ids) for ids in index.values() if len(ids)>1)
    return {'exact':groups(exact),'normalized':groups(normalized),'action':'diagnostic_only'}


def prepare_file_suite(base_suite: BenchmarkSuite, *, root, intake: dict[str, Any]):
    """Return (rebuilt suite, measured evidence); replace all inline documents.

    The caller's dates/trust remain declarations. read_at is an actual UTC byte
    observation and is never substituted for the declared content dates.
    """
    manifest = validate_intake(intake)
    if root is None: raise IntakeError('ROOT_REQUIRED')
    documents = []; observed = []; first = []
    for row in manifest['files']:
        metadata={k:v for k,v in row.items() if k not in {'name','size','media_type'}}
        doc=Document.from_dict({**metadata,'content':'metadata validation placeholder'})
        errors=[e for e in doc.validation_errors(base_suite.evaluation_date) if e!='hash_mismatch']
        if errors: raise IntakeError('DECLARED_CONTENT_REFUSED_' + errors[0].upper(),name=row['name'])
    with FileRoot(root) as reader:
        total = 0
        for row in manifest['files']:
            raw, identity = reader.read(row['name'], min(MAX_FILE_BYTES, MAX_TOTAL_BYTES-total))
            total += len(raw)
            actual = hashlib.sha256(raw).hexdigest()
            if len(raw)!=row['size']: raise IntakeError('SIZE_MISMATCH',name=row['name'])
            if actual!=row['sha256']: raise IntakeError('HASH_MISMATCH',name=row['name'])
            try:
                content=raw.decode('utf-8')
            except UnicodeError as exc:
                raise IntakeError('INVALID_UTF8',name=row['name']) from exc
            metadata={k:v for k,v in row.items() if k not in {'name','size','media_type'}}
            try:
                doc=Document.from_dict({**metadata,'content':content})
            except ContractError as exc:
                raise IntakeError('INVALID_DOCUMENT_CONTENT',name=row['name']) from exc
            documents.append(doc)
            first.append((row['name'],identity,actual))
            observed.append({'name':row['name'],'source_id':row['source_id'],'size':len(raw),
                             'sha256':actual,'read_at':datetime.now(timezone.utc).isoformat(),
                             'observed_at_declared':row['observed_at'],'expires_at_declared':row['expires_at'],
                             'trust_declared':row['trust'],'status':'read_and_verified'})
        # Reopen through the same pinned root and compare identities AND bytes.
        # A replacement with identical bytes still invalidates this capture.
        for name, identity, digest in first:
            raw, current = reader.read(name,MAX_FILE_BYTES)
            if current!=identity or hashlib.sha256(raw).hexdigest()!=digest:
                raise IntakeError('SOURCE_CHANGED',name=name)
    rebuilt=base_suite.to_dict()
    rebuilt['documents']=[doc.to_dict() for doc in documents]
    try:
        text=json.dumps(rebuilt,ensure_ascii=True,allow_nan=False)
        if len(text.encode('utf-8'))>MAX_SUITE_BYTES: raise IntakeError('SUITE_BYTE_LIMIT')
        suite=BenchmarkSuite.from_json(text)
    except ContractError as exc:
        if isinstance(exc, IntakeError): raise
        raise IntakeError('REBUILT_SUITE_INVALID') from exc
    evidence={'schema_version':'rag-lab/file-observation-v1','status':'measured',
              'template_suite_sha256':base_suite.digest,'suite_sha256':suite.digest,
              'intake_sha256':canonical_sha256(manifest),'replacement_policy':'replace_all_inline_documents',
              'document_count':len(documents),'total_bytes':total,'files':observed,
              'duplicates':duplicate_groups(documents),'dates_provenance':'caller_declared',
              'freshness_reference':'declared_suite_evaluation_date','source_origin_verified':False}
    return suite,evidence


def verify_observation(recorded, measured):
    """Match current bytes/metadata while retaining historical read_at values."""
    if not isinstance(recorded,dict) or set(recorded)!=set(measured):
        raise IntakeError('INTAKE_OBSERVATION_MISMATCH')
    try:
        expected=json.loads(json.dumps(measured))
        if len(recorded['files'])!=len(expected['files']): raise IntakeError('INTAKE_OBSERVATION_MISMATCH')
        for old,new in zip(recorded['files'],expected['files']):
            stamp=old['read_at']
            if not isinstance(stamp,str) or len(stamp)>64: raise IntakeError('INVALID_READ_TIMESTAMP')
            parsed=datetime.fromisoformat(stamp)
            if parsed.tzinfo is None or parsed.utcoffset() is None: raise IntakeError('INVALID_READ_TIMESTAMP')
            if parsed>datetime.now(timezone.utc): raise IntakeError('READ_TIMESTAMP_IN_FUTURE')
            new['read_at']=stamp
        if recorded!=expected: raise IntakeError('INTAKE_OBSERVATION_MISMATCH')
    except (TypeError,ValueError,KeyError) as exc:
        if isinstance(exc,IntakeError):raise
        raise IntakeError('INTAKE_OBSERVATION_MISMATCH') from exc
