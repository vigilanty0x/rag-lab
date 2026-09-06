"""Synthetic file intake through the real canonical workflow."""
from dataclasses import replace
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from fixtures import suite
from rag_quality_bench.models import ContractError
from rag_quality_bench.workflow import run_workflow, verify_workflow


def file_fixture(tmp_path):
    root=tmp_path/'inputs';root.mkdir()
    template=suite();doc=template.documents[0]
    text='  Café\r\nThe public handbook says the launch city is Geneva\tand the launch color is teal.  '
    raw=text.encode('utf-8');(root/'handbook.txt').write_bytes(raw)
    metadata=doc.to_dict();metadata.pop('content')
    metadata.update(sha256=hashlib.sha256(raw).hexdigest())
    manifest={'schema_version':'rag-lab/file-intake-v1','files':[
        {**metadata,'name':'handbook.txt','size':len(raw),'media_type':'text/plain'}]}
    return template,root,manifest,text


def test_intake_workflow_reads_and_replays_original_unicode_bytes(tmp_path):
    template,root,manifest,text=file_fixture(tmp_path)
    out=tmp_path/'workflow'
    receipt=run_workflow(template,root=root,intake=manifest,query='launch city',output=out)
    assert receipt['schema_version']=='rag-lab/workflow-v4'
    assert receipt['template_suite_sha256']==template.digest
    assert receipt['suite_sha256']!=template.digest
    assert verify_workflow(out,template,root=root,intake=manifest)==receipt
    search=json.loads((out/'search.json').read_bytes())
    for hit in search['hits']:
        assert text[hit['char_start']:hit['char_end']]==hit['quote']
    assert (root/'handbook.txt').read_bytes()==text.encode('utf-8')


def test_intake_missing_file_refuses_before_results(tmp_path):
    template,root,manifest,_=file_fixture(tmp_path);manifest['files'][0]['name']='missing.txt'
    with pytest.raises(ContractError,match='FILE_MISSING'):
        run_workflow(template,root=root,intake=manifest,query='launch city',output=tmp_path/'none')
    assert not (tmp_path/'none').exists()


def test_old_file_receipt_refuses_after_bytes_change(tmp_path):
    template,root,manifest,_=file_fixture(tmp_path);out=tmp_path/'workflow'
    run_workflow(template,root=root,intake=manifest,query='launch city',output=out)
    (root/'handbook.txt').write_bytes(b'changed synthetic contents')
    with pytest.raises(ContractError):verify_workflow(out,template,root=root,intake=manifest)


def original(project, package, name='core.py'):
    import importlib.util
    path=Path(__file__).resolve().parents[1]/'packages'/project/'src'/package/name
    spec=importlib.util.spec_from_file_location('oracle_'+package,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('name', ['../x','/x','a/../x','a//x','a\\x','','\ud800','C:/x','a:stream','.env','.ENV','nul.txt','folder./x'])
def test_paths_rejected_before_reader_open(tmp_path,name,monkeypatch):
    import rag_quality_bench.file_intake as module
    template,root,manifest,_=file_fixture(tmp_path);manifest['files'][0]['name']=name
    monkeypatch.setattr(module,'FileRoot',lambda *a,**k:pytest.fail('reader opened for invalid manifest'))
    with pytest.raises(ContractError):module.prepare_file_suite(template,root=root,intake=manifest)


def test_actual_file_intake_oracle_agrees_on_valid_and_invalid_metadata(tmp_path):
    from rag_quality_bench.file_intake import validate_intake
    legacy=original('file-intake-pipeline','file_intake_pipeline','__init__.py')
    _,_,manifest,_=file_fixture(tmp_path);row=manifest['files'][0]
    select=lambda v:{k:v[k] for k in ['name','size','sha256','media_type']}
    assert legacy.intake([select(row)])['accepted']
    assert validate_intake(manifest)['files']==[row]
    for field,value in [('name','../escape'),('size',True),('sha256','A'*64),('media_type','image/png')]:
        altered=deepcopy(manifest);altered['files'][0][field]=value
        assert legacy.intake([select(altered['files'][0])])['accepted'] is False
        with pytest.raises(ContractError):validate_intake(altered)


@pytest.mark.parametrize('field,value', [('size',0),('size',800001),('size',True),('sha256','bad'),('media_type',[]),('source_id','UPPER'),('observed_at',None),('observed_at','not-date'),('expires_at','bad'),('trust','unknown')])
def test_invalid_metadata_is_typed_refusal_before_io(tmp_path,field,value,monkeypatch):
    import rag_quality_bench.file_intake as module
    template,root,manifest,_=file_fixture(tmp_path);manifest['files'][0][field]=value
    monkeypatch.setattr(module,'FileRoot',lambda *a,**k:pytest.fail('invalid metadata opened reader'))
    with pytest.raises(ContractError):module.prepare_file_suite(template,root=root,intake=manifest)


@pytest.mark.parametrize('field,value,code', [('observed_at','2028-01-01','OBSERVED_IN_FUTURE'),('expires_at','2020-01-01','EXPIRED'),('trust','untrusted','TRUST_UNTRUSTED'),('trust','blocked','TRUST_BLOCKED')])
def test_declared_dates_and_trust_are_never_replaced_by_current_read(tmp_path,field,value,code,monkeypatch):
    import rag_quality_bench.file_intake as module
    template,root,manifest,_=file_fixture(tmp_path);manifest['files'][0][field]=value
    monkeypatch.setattr(module,'FileRoot',lambda *a,**k:pytest.fail('refused document opened reader'))
    with pytest.raises(ContractError,match=code):module.prepare_file_suite(template,root=root,intake=manifest)


def test_freshness_matches_real_date_source_at_explicit_midnight():
    legacy=original('data-freshness-monitor','data_freshness_monitor')
    doc=suite().documents[0]
    for observed,status in [('2026-08-14','fresh'),('2026-08-16','future')]:
        result=legacy.monitor([{'id':doc.source_id,'observed_at':observed+'T00:00:00+00:00'}],now='2026-08-15T00:00:00+00:00',default_max_age_seconds=86400)
        assert result['datasets'][0]['status']==status
        from datetime import date
        errors=replace(doc,observed_at=date.fromisoformat(observed)).validation_errors(suite().evaluation_date)
        assert ('observed_in_future' in errors)==(status=='future')
    assert legacy.monitor([{'id':'missing'}],now='2026-08-15T00:00:00Z')['datasets'][0]['status']=='blocked'


@pytest.mark.parametrize('kind', ['case-name','source-id','extra-field','empty','too-many','total'])
def test_manifest_ambiguity_and_bounds(tmp_path,kind):
    from rag_quality_bench.file_intake import validate_intake
    _,_,manifest,_=file_fixture(tmp_path);row=manifest['files'][0]
    if kind=='case-name':manifest['files'].append({**row,'name':row['name'].upper(),'source_id':'second'})
    elif kind=='source-id':manifest['files'].append({**row,'name':'other.txt'})
    elif kind=='extra-field':row['extra']=True
    elif kind=='empty':manifest['files']=[]
    elif kind=='too-many':manifest['files']=[row]*201
    else:manifest['files']=[{**row,'name':f'{i}.txt','source_id':f'doc-{i}','size':800000} for i in range(6)]
    with pytest.raises(ContractError):validate_intake(manifest)


@pytest.mark.parametrize('kind',['size','hash','utf8','characters'])
def test_real_file_refusals_preserve_inputs_and_no_output(tmp_path,kind):
    template,root,manifest,_=file_fixture(tmp_path);row=manifest['files'][0];path=root/'handbook.txt'
    if kind=='size':row['size']+=1
    elif kind=='hash':row['sha256']='0'*64
    else:
        raw=b'\xff' if kind=='utf8' else b'a'*200001
        path.write_bytes(raw);row.update(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    before=path.read_bytes()
    with pytest.raises(ContractError):run_workflow(template,root=root,intake=manifest,query='launch',output=tmp_path/'refused')
    assert path.read_bytes()==before and not (tmp_path/'refused').exists()


def test_inline_documents_replaced_not_merged_and_dates_are_separate(tmp_path):
    from datetime import datetime,timezone
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,text=file_fixture(tmp_path)
    secret=replace(template.documents[0],source_id='inline-only',content='synthetic inline sentinel excluded')
    template=replace(template,documents=(*template.documents,secret))
    start=datetime.now(timezone.utc)
    rebuilt,evidence=prepare_file_suite(template,root=root,intake=manifest)
    assert [d.source_id for d in rebuilt.documents]==['handbook']
    assert rebuilt.documents[0].content==text
    row=evidence['files'][0]
    assert start<=datetime.fromisoformat(row['read_at'])<=datetime.now(timezone.utc)
    assert row['observed_at_declared']=='2026-08-14'
    assert evidence['source_origin_verified'] is False
    assert 'synthetic inline sentinel' not in json.dumps(evidence)
    out=tmp_path/'workflow';run_workflow(template,root=root,intake=manifest,query='launch',output=out)
    assert all(b'synthetic inline sentinel' not in p.read_bytes() for p in out.iterdir())


def test_duplicate_groups_match_real_finder_without_changing_documents(tmp_path):
    import importlib.util
    from rag_quality_bench.file_intake import prepare_file_suite
    path=Path(__file__).parent/'oracles/duplicate_finder_core.py'
    assert hashlib.sha256(path.read_bytes()).hexdigest()=='a8ac6aebf2f2180e6fa596e1871c098ffd48be28c3e5fcdbeb91180dd775d221'
    spec=importlib.util.spec_from_file_location('duplicate_original',path);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    template,root,manifest,text=file_fixture(tmp_path);first=manifest['files'][0]
    for identifier,content in [('copy',text),('normalized',' '.join(text.strip().casefold().split()))]:
        raw=content.encode();(root/(identifier+'.txt')).write_bytes(raw)
        manifest['files'].append({**first,'name':identifier+'.txt','source_id':identifier,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    rebuilt,evidence=prepare_file_suite(template,root=root,intake=manifest)
    records=[{'id':d.source_id,'content':d.content} for d in rebuilt.documents]
    expected=old.find(records,['content'])
    assert {k:evidence['duplicates'][k] for k in expected}==expected
    assert len(rebuilt.documents)==3 and len(list(root.iterdir()))==3
    assert evidence['duplicates']['action']=='diagnostic_only'
    doctor=original('rag-corpus-doctor','rag_corpus_doctor')
    assert doctor.evaluate({'documents':3,'indexed':3,'duplicates':1})['status']=='failed'
    assert evidence['status']=='measured'  # A measurement is not that doctor's healthy verdict.


def test_change_between_byte_passes_refused(tmp_path,monkeypatch):
    from rag_quality_bench.file_intake import prepare_file_suite
    from rag_quality_bench.intake_io import FileRoot
    template,root,manifest,_=file_fixture(tmp_path);actual=FileRoot.read;count=0
    def changed(self,name,maximum):
        nonlocal count
        result=actual(self,name,maximum);count+=1
        if count==1:(root/name).write_bytes(b'changed after first read')
        return result
    monkeypatch.setattr(FileRoot,'read',changed)
    with pytest.raises(ContractError,match='SOURCE_CHANGED'):prepare_file_suite(template,root=root,intake=manifest)


def test_same_bytes_replacement_between_passes_refused(tmp_path,monkeypatch):
    from rag_quality_bench.file_intake import prepare_file_suite
    from rag_quality_bench.intake_io import FileRoot
    template,root,manifest,text=file_fixture(tmp_path);actual=FileRoot.read;count=0;blocked=[]
    def changed(self,name,maximum):
        nonlocal count
        result=actual(self,name,maximum);count+=1
        if count==1:
            fresh=root/'replacement.txt';fresh.write_bytes(text.encode())
            try:fresh.replace(root/name)
            except OSError as exc:
                if os.name!='nt' or getattr(exc,'winerror',None)!=32:raise
                blocked.append('sharing_violation')
        return result
    monkeypatch.setattr(FileRoot,'read',changed)
    try:
        rebuilt,_=prepare_file_suite(template,root=root,intake=manifest)
    except ContractError as exc:
        assert 'SOURCE_CHANGED' in str(exc) and not blocked
    else:
        assert blocked==['sharing_violation'] and rebuilt.documents[0].content==text


def test_hardlinks_refused_before_byte_read(tmp_path):
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,_=file_fixture(tmp_path)
    os.link(root/'handbook.txt',tmp_path/'alias.txt')
    with pytest.raises(ContractError,match='NON_REGULAR_OR_LINKED'):prepare_file_suite(template,root=root,intake=manifest)


@pytest.mark.parametrize('place',['file','subdir','root'])
def test_symlink_or_junction_route_is_refused(tmp_path,place):
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,_=file_fixture(tmp_path)
    try:
        if place=='file':
            link=root/'link.txt';link.symlink_to(root/'handbook.txt');manifest['files'][0]['name']='link.txt'
        else:
            link=tmp_path/'linked-dir';link.symlink_to(root,target_is_directory=True)
            if place=='root':root=link
            else:root=tmp_path;manifest['files'][0]['name']='linked-dir/handbook.txt'
    except OSError as exc:
        if os.name=='nt' and getattr(exc,'winerror',None)==1314:pytest.skip('Windows symlink privilege unavailable; actual POSIX run covers links')
        raise
    with pytest.raises(ContractError):prepare_file_suite(template,root=root,intake=manifest)


@pytest.mark.skipif(os.name!='posix',reason='POSIX descriptor-directory swap')
def test_directory_swap_while_descriptor_open_refuses(tmp_path,monkeypatch):
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,_=file_fixture(tmp_path);read=os.read;attempted=False
    def swapping(fd,size):
        nonlocal attempted
        if not attempted:
            attempted=True;root.rename(tmp_path/'moved');root.mkdir();(root/'handbook.txt').write_bytes(b'outside replacement')
        return read(fd,size)
    monkeypatch.setattr(os,'read',swapping)
    with pytest.raises(ContractError,match='SOURCE_CHANGED'):prepare_file_suite(template,root=root,intake=manifest)
    assert attempted


@pytest.mark.skipif(os.name!='nt',reason='Windows sharing/handle semantics')
def test_windows_directory_rename_is_blocked_during_actual_read(tmp_path,monkeypatch):
    from rag_quality_bench.file_intake import prepare_file_suite
    from rag_quality_bench.intake_io import _WindowsReader
    template,root,manifest,_=file_fixture(tmp_path);read=_WindowsReader.read;attempted=[]
    def swapping(self,handle,maximum):
        with pytest.raises(OSError):root.rename(tmp_path/'moved')
        attempted.append(True);return read(self,handle,maximum)
    monkeypatch.setattr(_WindowsReader,'read',swapping)
    rebuilt,_=prepare_file_suite(template,root=root,intake=manifest)
    assert len(attempted)==2 and len(rebuilt.documents)==1


@pytest.mark.skipif(os.name!='nt',reason='Windows junction semantics')
@pytest.mark.parametrize('place',['root','subdir'])
def test_actual_windows_junction_is_refused(tmp_path,place):
    import _winapi, stat
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,_=file_fixture(tmp_path);link=tmp_path/'junction'
    _winapi.CreateJunction(str(root),str(link))
    metadata=link.lstat()
    assert metadata.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    assert metadata.st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
    if place=='root':root=link
    else:root=tmp_path;manifest['files'][0]['name']='junction/handbook.txt'
    with pytest.raises(ContractError,match='NON_REGULAR_OR_LINKED'):
        prepare_file_suite(template,root=root,intake=manifest)


@pytest.mark.skipif(os.name!='nt',reason='Windows directory WRITE-sharing denial')
def test_windows_parent_write_handle_cannot_be_opened_during_read(tmp_path,monkeypatch):
    from rag_quality_bench.file_intake import prepare_file_suite
    from rag_quality_bench.intake_io import _WindowsReader
    template,root,manifest,_=file_fixture(tmp_path);read=_WindowsReader.read;attempted=[]
    def reparse_attempt(self,handle,maximum):
        attempted.append(True)
        candidate=self.kernel.CreateFileW(str(root),0x40000000,7,None,3,0x02200000,None)
        if candidate!=self.w.HANDLE(-1).value:
            self.kernel.CloseHandle(candidate)
            pytest.fail('ancestor accepted a write-capable handle during intake')
        assert self.c.get_last_error()==32  # sharing violation, not a permissions change
        return read(self,handle,maximum)
    monkeypatch.setattr(_WindowsReader,'read',reparse_attempt)
    prepare_file_suite(template,root=root,intake=manifest)
    assert len(attempted)==2


def test_concurrent_readers_share_no_mutable_state(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,text=file_fixture(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:prepare_file_suite(template,root=root,intake=manifest),range(2)))
    assert results[0][0].digest==results[1][0].digest
    assert (root/'handbook.txt').read_bytes()==text.encode()


def test_intake_and_supplied_vectors_bind_rebuilt_suite(tmp_path):
    from rag_quality_bench.file_intake import prepare_file_suite
    from rag_quality_bench.engine import chunk_document
    from rag_quality_bench.models import content_sha256
    template,root,manifest,_=file_fixture(tmp_path);template=replace(template,retrieval_strategy='supplied')
    rebuilt,_=prepare_file_suite(template,root=root,intake=manifest)
    from test_supplied_vectors import vector_fixture
    _,vectors=vector_fixture();vectors['suite_sha256']=rebuilt.digest
    row=vectors['chunks'][0]
    vectors['chunks']=[{**row,'id':c.chunk_id,'text_sha256':content_sha256(c.text),'vector':[1,0]} for d in rebuilt.documents for c in chunk_document(d,rebuilt.chunk_size,rebuilt.chunk_overlap)]
    vectors['queries']=[{**row,'id':content_sha256(q),'text_sha256':content_sha256(q),'vector':[1,0]} for q in [*[q.text for q in rebuilt.questions],'launch city']]
    out=tmp_path/'supplied';receipt=run_workflow(template,root=root,intake=manifest,vectors=vectors,query='launch city',output=out,minimum_pass_rate=0)
    assert receipt['schema_version']=='rag-lab/workflow-v4' and 'vectors_sha256' in receipt
    assert verify_workflow(out,template,root=root,intake=manifest,vectors=vectors)==receipt
    vectors['suite_sha256']=template.digest
    with pytest.raises(ContractError,match='suite identity'):run_workflow(template,root=root,intake=manifest,vectors=vectors,query='launch city',output=tmp_path/'wrong')
    assert not (tmp_path/'wrong').exists()


def test_versioned_intake_and_cli_roundtrip(tmp_path,capsys):
    from rag_quality_bench.cli import main
    template,root,manifest,_=file_fixture(tmp_path)
    template_path=tmp_path/'template.json';template_path.write_text(json.dumps(template.to_dict()))
    manifest_path=tmp_path/'manifest.json';manifest_path.write_text(json.dumps(manifest))
    out=tmp_path/'cli';common=['--suite',str(template_path),'--input-root',str(root),'--intake',str(manifest_path),'--previous-suite',str(template_path)]
    assert main(['workflow',*common,'--query','launch city','--output',str(out)])==0
    receipt=json.loads(capsys.readouterr().out)
    assert receipt['schema_version']=='rag-lab/workflow-v4' and 'corpus_diff_sha256' in receipt
    assert main(['verify-workflow',*common,'--output',str(out)])==0
    assert json.loads(capsys.readouterr().out)['valid'] is True


@pytest.mark.parametrize('artifact',['intake.json','file-observation.json','suite.json'])
def test_new_artifact_tampering_rejected_even_rehashed(tmp_path,artifact):
    from rag_quality_bench.models import canonical_sha256
    template,root,manifest,_=file_fixture(tmp_path);out=tmp_path/'workflow'
    receipt=run_workflow(template,root=root,intake=manifest,query='launch city',output=out)
    path=out/artifact;value=json.loads(path.read_bytes())
    if artifact=='intake.json':value['files'][0]['title']='forged'
    elif artifact=='file-observation.json':value['files'][0]['sha256']='0'*64
    else:value['documents'][0]['content']='forged'
    path.write_text(json.dumps(value));receipt['artifacts'][artifact]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
    receipt['receipt_sha256']=canonical_sha256({k:v for k,v in receipt.items() if k!='receipt_sha256'})
    (out/'workflow.json').write_text(json.dumps(receipt))
    with pytest.raises(ContractError):verify_workflow(out,template,root=root,intake=manifest)


def test_citation_view_uses_actual_original_quote_span_oracle(tmp_path):
    template,root,manifest,text=file_fixture(tmp_path);out=tmp_path/'workflow'
    run_workflow(template,root=root,intake=manifest,query='launch city',output=out)
    search=json.loads((out/'search.json').read_bytes());hit=search['hits'][0]
    source=original('rag-citation-explorer','rag_citation_explorer')
    value={'answer':'launch city','claims':[{'id':'claim','text':'launch city'}],
           'sources':[{'source_id':hit['source_id'],'chunks':[{'chunk_id':'whole-document','text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()}]}],
           'citations':[{'claim_id':'claim','source_id':hit['source_id'],'chunk_id':'whole-document','quote':hit['quote'],'start':hit['char_start'],'end':hit['char_end']}]}
    assert source.build_citation_view(value)['structural_coverage']==1
    bad=deepcopy(value);bad['citations'][0]['start']+=1
    with pytest.raises(ValueError,match='exactly match'):source.build_citation_view(bad)


@pytest.mark.skipif(os.name!='posix',reason='POSIX FIFO, must never block')
def test_fifo_is_refused_without_reading(tmp_path,monkeypatch):
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,_=file_fixture(tmp_path);os.mkfifo(root/'fifo')
    manifest['files'][0]['name']='fifo'
    monkeypatch.setattr(os,'read',lambda *a:pytest.fail('attempted FIFO byte read'))
    with pytest.raises(ContractError,match='NON_REGULAR_OR_LINKED'):prepare_file_suite(template,root=root,intake=manifest)


def test_all_handles_close_on_success_and_failure(tmp_path):
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,text=file_fixture(tmp_path)
    prepare_file_suite(template,root=root,intake=manifest)
    moved=tmp_path/'moved';root.rename(moved);moved.rename(root)
    manifest['files'][0]['sha256']='0'*64
    with pytest.raises(ContractError):prepare_file_suite(template,root=root,intake=manifest)
    root.rename(moved);moved.rename(root)
    assert (root/'handbook.txt').read_bytes()==text.encode()


def test_json_loader_and_root_presence_are_fail_closed(tmp_path):
    from rag_quality_bench.file_intake import load_intake,prepare_file_suite
    template,root,manifest,_=file_fixture(tmp_path);path=tmp_path/'manifest.json'
    for value in ['{"files":[],"files":[]}','{"x":NaN}','[]','['*1500+']'*1500]:
        path.write_text(value)
        with pytest.raises(ContractError):load_intake(path)
    with pytest.raises(ContractError,match='ROOT_REQUIRED'):prepare_file_suite(template,root=None,intake=manifest)
    with pytest.raises(ContractError):run_workflow(template,root=root,query='launch',output=tmp_path/'without-manifest')


def test_new_receipt_requires_same_manifest_and_root(tmp_path):
    template,root,manifest,_=file_fixture(tmp_path);out=tmp_path/'workflow'
    run_workflow(template,root=root,intake=manifest,query='launch city',output=out)
    with pytest.raises(ContractError):verify_workflow(out,template)
    altered=deepcopy(manifest);altered['files'][0]['title']='other declaration'
    with pytest.raises(ContractError,match='manifest replay'):verify_workflow(out,template,root=root,intake=altered)
    with pytest.raises(ContractError):verify_workflow(out,template,root=tmp_path/'absent-root',intake=manifest)


def test_receipt_read_time_remains_historical_on_replay(tmp_path):
    from rag_quality_bench.file_intake import prepare_file_suite
    template,root,manifest,_=file_fixture(tmp_path);out=tmp_path/'workflow'
    receipt=run_workflow(template,root=root,intake=manifest,query='launch city',output=out)
    before=(out/'file-observation.json').read_bytes()
    assert verify_workflow(out,template,root=root,intake=manifest)==receipt
    assert (out/'file-observation.json').read_bytes()==before
    _,new=prepare_file_suite(template,root=root,intake=manifest)
    assert new['files'][0]['read_at']>=json.loads(before)['files'][0]['read_at']


def test_future_recorded_read_time_is_refused(tmp_path):
    from rag_quality_bench.file_intake import prepare_file_suite,verify_observation
    template,root,manifest,_=file_fixture(tmp_path);_,measurement=prepare_file_suite(template,root=root,intake=manifest)
    bad=deepcopy(measurement);bad['files'][0]['read_at']='2999-01-01T00:00:00+00:00'
    with pytest.raises(ContractError,match='READ_TIMESTAMP_IN_FUTURE'):verify_observation(bad,measurement)


def test_serialized_suite_byte_limit_is_typed_and_keeps_sources(tmp_path):
    from rag_quality_bench.file_intake import prepare_file_suite, IntakeError
    template,root,manifest,_=file_fixture(tmp_path)
    original=manifest['files'][0];raw=('界'*200_000).encode('utf-8')
    rows=[]
    for i in range(5):
        name=f'large-{i}.txt';(root/name).write_bytes(raw)
        rows.append({**original,'name':name,'source_id':'handbook' if i==0 else f'extra-{i}',
                     'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)})
    manifest['files']=rows
    with pytest.raises(IntakeError,match='SUITE_BYTE_LIMIT') as caught:
        prepare_file_suite(template,root=root,intake=manifest)
    assert caught.value.code=='SUITE_BYTE_LIMIT'
    assert all((root/row['name']).read_bytes()==raw for row in rows)


def test_documented_example_runs_real_cli_and_replay(tmp_path,capsys):
    from rag_quality_bench.cli import main
    source=Path(__file__).resolve().parents[1]/'examples'
    root=tmp_path/'inputs';root.mkdir()
    (root/'handbook.txt').write_bytes((source/'intake-files/handbook.txt').read_bytes())
    template=tmp_path/'template.json';template.write_bytes((source/'intake-template.json').read_bytes())
    manifest=tmp_path/'manifest.json';manifest.write_bytes((source/'intake-manifest.json').read_bytes())
    common=['--suite',str(template),'--input-root',str(root),'--intake',str(manifest),'--output',str(tmp_path/'receipt')]
    assert main(['workflow',*common,'--query','launch city'])==0
    receipt=json.loads(capsys.readouterr().out)
    assert receipt['schema_version']=='rag-lab/workflow-v4' and receipt['status']=='completed'
    assert main(['verify-workflow',*common])==0
    assert json.loads(capsys.readouterr().out)['valid'] is True
