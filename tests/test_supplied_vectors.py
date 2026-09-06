"""Supplied vector parity uses the retained source engines as actual oracles."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from fixtures import suite
from rag_quality_bench.engine import BenchmarkEngine, chunk_document
from rag_quality_bench.models import ContractError, content_sha256
from rag_quality_bench.workflow import run_workflow, verify_workflow


def vector_fixture(weight=0.5):
    original = suite()
    text = 'Launch launch a café alpha unrelated example public synthetic material.'
    doc = replace(original.documents[0], content=text, sha256=content_sha256(text))
    other = replace(doc, source_id='other', content='Nothing about launch here.', sha256=content_sha256('Nothing about launch here.'))
    model = replace(original, documents=(doc, other), chunk_size=50,
                    retrieval_strategy='supplied', hybrid_weight=weight)
    chunks = [c for d in sorted(model.documents, key=lambda d: d.source_id)
              for c in chunk_document(d, model.chunk_size, model.chunk_overlap)]
    def row(identifier, text_digest, vector):
        return {'id': identifier, 'text_sha256': text_digest, 'model': 'synthetic-space',
                'model_version': 'fixture-v1', 'vector': vector}
    query_texts = [q.text for q in model.questions] + ['launch café a']
    payload = {'schema_version': 'rag-lab/vectors-v1', 'suite_sha256': model.digest,
               'model': 'synthetic-space', 'model_version': 'fixture-v1', 'dimension': 2,
               'provenance': {'kind': 'caller_declared', 'reference': 'synthetic-unit-fixture',
                              'artifact_sha256': 'a' * 64},
               'chunks': [row(c.chunk_id, content_sha256(c.text), v)
                          for c, v in zip(chunks, ([3, 4], [-4, -3]))],
               'queries': [row(content_sha256(q), content_sha256(q), [1, 0]) for q in query_texts]}
    return model, payload


def test_supplied_workflow_replays_actual_vectors(tmp_path):
    model, payload = vector_fixture()
    out = tmp_path / 'vector-workflow'
    receipt = run_workflow(model, vectors=payload, query='launch café a', output=out, minimum_pass_rate=0)
    assert receipt['schema_version'] == 'rag-lab/workflow-v3'
    assert receipt['score_kind'] == 'lexical_frequency_and_supplied_cosine_rank'
    assert receipt['embedding_origin_verified'] is False
    assert receipt['provider_called'] is False
    assert receipt['query_quality'] == 'not_measured'
    assert verify_workflow(out, model, vectors=payload) == receipt
    search = json.loads((out / 'search.json').read_bytes())
    assert search['confidence'] is None
    assert search['hits'][-1]['vector_score'] < 0
    assert json.loads((out / 'vectors.json').read_bytes()) == payload


def test_missing_query_vector_refuses_before_output(tmp_path):
    model, payload = vector_fixture()
    with pytest.raises(ContractError, match='query vector'):
        run_workflow(model, vectors=payload, query='not supplied', output=tmp_path / 'missing')
    assert not (tmp_path / 'missing').exists()


def test_zero_vector_refuses_before_output(tmp_path):
    model, payload = vector_fixture()
    payload['chunks'][0]['vector'] = [0, 0]
    with pytest.raises(ContractError, match='zero_vector'):
        run_workflow(model, vectors=payload, query='launch café a', output=tmp_path / 'zero')
    assert not (tmp_path / 'zero').exists()


def source_engine(project, package):
    import importlib.util
    path = Path(__file__).resolve().parents[1] / 'packages' / project / 'src' / package / 'core.py'
    spec = importlib.util.spec_from_file_location('retained_' + package, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('weight', [0, .2, .5, 1])
@pytest.mark.parametrize('vectors', [([3,4],[-4,-3]), ([0,1],[0,-1]), ([1,0],[1,0]), ([1e200,1e200],[-1e200,1e200]), ([5e-324,0],[0,5e-324])],
                         ids=['signed','zero-cosine','ties','large-finite','subnormal'])
def test_ranking_and_components_equal_actual_hybrid_source(weight, vectors):
    from rag_quality_bench.retrieval import RetrievalIndex
    model, payload = vector_fixture(weight)
    for row, vector in zip(payload['chunks'], vectors): row['vector'] = list(vector)
    engine = BenchmarkEngine(model, vectors=payload)
    chunks = engine._index({d.source_id:d for d in model.documents})
    index = RetrievalIndex(chunks, strategy='supplied', hybrid_weight=weight, vectors=engine.vectors)
    query = 'launch café a'
    original = source_engine('hybrid-search-playground', 'hybrid_search_playground')
    rows = original.search(query, [{'id':c.chunk_id, 'text':c.text, 'vector':list(v), 'query_vector':[1,0]} for c,v in zip(chunks,vectors)], alpha=weight, limit=20)
    actual = index.rank(query, limit=20)
    assert [r.chunk.chunk_id for r in actual] == [r['id'] for r in rows]
    assert [(r.score,r.lexical_score,r.vector_score) for r in actual] == [(r['score'],r['lexical'],r['semantic']) for r in rows]


@pytest.mark.parametrize('vector,issue', [([1], 'dimension'), ([0,0], 'zero_vector'), ([float('nan'),1], 'non_finite'), ([float('inf'),1], 'non_finite'), ([True,0], 'non_finite')])
def test_real_doctor_rejections_are_preserved(vector, issue):
    doctor = source_engine('semantic-index-doctor', 'semantic_index_doctor')
    assert doctor.diagnose([{'id':'chunk', 'vector':vector}], expected_dimension=2)['issues'][0]['issue'] == issue
    model, payload = vector_fixture(); payload['chunks'][0]['vector'] = vector
    with pytest.raises(ContractError, match=issue): BenchmarkEngine(model, vectors=payload)


def test_real_embedding_lab_scope_is_counts_only_and_not_provider_proof():
    old = source_engine('embedding-lab', 'embedding_lab')
    assert old.evaluate({'model':'synthetic', 'dimensions':2, 'vector_count':2})['status'] == 'passed'
    assert old.evaluate({'model':'synthetic', 'dimensions':0, 'vector_count':2})['status'] == 'failed'
    assert old.evaluate({'model':'synthetic', 'dimensions':2, 'vector_count':0})['status'] == 'failed'
    model, payload = vector_fixture()
    value = BenchmarkEngine(model, vectors=payload).search('launch café a')
    assert value['embedding_model']['origin_verified'] is False
    assert value['embedding_model']['provider_called'] is False


@pytest.mark.parametrize('target,field,value', [
    ('root','dimension',True), ('root','dimension',0), ('root','dimension',4097),
    ('root','suite_sha256','0'*64), ('root','schema_version','future'),
    ('chunk','model','other'), ('chunk','model_version','other'), ('chunk','id','unknown'),
    ('chunk','text_sha256','0'*64), ('chunk','vector',[1.7e308,1.7e308]),
    ('chunk','vector',[10**1000,0]), ('query','model','other'), ('query','model_version','other'),
    ('query','text_sha256','0'*64), ('query','id','bad-id'), ('query','vector',[0,0]),
    ('root','provenance',{'kind':'verified','reference':'unproved','artifact_sha256':'a'*64}),
    ('root','model',''), ('root','model_version','x'*257),
])
def test_payload_identity_types_and_numeric_bounds_refuse_before_index(target, field, value, monkeypatch):
    import rag_quality_bench.engine as module
    model, payload = vector_fixture()
    row = payload if target=='root' else payload['chunks' if target=='chunk' else 'queries'][0]
    row[field] = value
    def forbidden(*args, **kwargs): pytest.fail('RetrievalIndex constructed before vector rejection')
    monkeypatch.setattr(module, 'RetrievalIndex', forbidden)
    with pytest.raises(ContractError): BenchmarkEngine(model, vectors=payload)


@pytest.mark.parametrize('group', ['chunks','queries'])
def test_duplicate_ids_refused_in_both_groups(group):
    model,payload=vector_fixture(); payload[group].append(deepcopy(payload[group][0]))
    with pytest.raises(ContractError, match='duplicate_id'): BenchmarkEngine(model,vectors=payload)


@pytest.mark.parametrize('mutation', ['missing-chunk','extra-chunk','missing-question','empty-chunks','unknown-field'])
def test_coverage_and_shape_are_exact(mutation):
    model,payload=vector_fixture()
    if mutation=='missing-chunk': payload['chunks'].pop()
    elif mutation=='extra-chunk': payload['chunks'].append({**payload['chunks'][0],'id':'extra'})
    elif mutation=='missing-question': payload['queries'].pop(0)
    elif mutation=='empty-chunks': payload['chunks']=[]
    else: payload['extra']=True
    with pytest.raises(ContractError): BenchmarkEngine(model,vectors=payload)


@pytest.mark.parametrize('bound', ['bytes','scalars','chunks','queries'])
def test_each_global_bound_fails_closed(bound, monkeypatch):
    from rag_quality_bench import supplied_vectors as module
    constant={'bytes':'MAX_VECTOR_BYTES','scalars':'MAX_VECTOR_SCALARS','chunks':'MAX_VECTOR_CHUNKS','queries':'MAX_VECTOR_QUERIES'}[bound]
    monkeypatch.setattr(module,constant,1)
    model,payload=vector_fixture()
    with pytest.raises(ContractError): BenchmarkEngine(model,vectors=payload)


def test_real_scalar_limit_is_enforced_before_vectors_are_materialized():
    model,payload=vector_fixture(); payload['dimension']=4096
    payload['queries']=[payload['queries'][0]]*243
    assert (len(payload['queries'])+len(payload['chunks']))*4096 > 1_000_000
    with pytest.raises(ContractError, match='total scalar'): BenchmarkEngine(model,vectors=payload)


def test_validated_snapshot_cannot_change_with_input_or_forged_maps():

    model,payload=vector_fixture(); engine=BenchmarkEngine(model,vectors=payload)
    before=engine.search('launch café a'); payload['chunks'][0]['vector']=[-1,0]
    assert engine.search('launch café a')==before
    validated=engine.vectors
    with pytest.raises(TypeError): validated.chunks['bad']=(1,0)
    forged=replace(validated,chunks={'bad':(1,0)},queries={},digest='0'*64)
    assert BenchmarkEngine(model,vectors=forged).search('launch café a')==before


def test_no_implicit_fallback_or_vector_loading_in_historical_modes():
    model,payload=vector_fixture()
    with pytest.raises(ContractError): BenchmarkEngine(model)
    for strategy in ['overlap','bm25','tfidf','hybrid']:
        with pytest.raises(ContractError,match='only allowed'): BenchmarkEngine(replace(model,retrieval_strategy=strategy),vectors=payload)


def test_json_loader_rejects_duplicates_constants_size_and_deep_nesting(tmp_path, monkeypatch):
    from rag_quality_bench.supplied_vectors import load_vectors
    from rag_quality_bench import supplied_vectors as module
    path=tmp_path/'vectors.json'
    for text in ['{"model":"a","model":"b"}', '{"x":NaN}', '[]', '['*1500+']'*1500]:
        path.write_text(text,encoding='utf-8')
        with pytest.raises(ContractError): load_vectors(path)
    monkeypatch.setattr(module,'MAX_VECTOR_BYTES',8);path.write_bytes(b' '*9)
    with pytest.raises(ContractError,match='byte bound'): load_vectors(path)


@pytest.mark.parametrize('versioned', [False,True])
def test_v3_preserves_optional_corpus_diff(tmp_path, versioned):
    model,payload=vector_fixture(); previous=suite() if versioned else None
    out=tmp_path/'workflow'
    receipt=run_workflow(model,vectors=payload,query='launch café a',output=out,previous_suite=previous,minimum_pass_rate=0)
    assert verify_workflow(out,model,vectors=payload,previous_suite=previous)==receipt
    assert ('previous_suite_sha256' in receipt) is versioned
    with pytest.raises(ContractError): verify_workflow(out,model)
    if versioned:
        with pytest.raises(ContractError): verify_workflow(out,model,vectors=payload)


@pytest.mark.parametrize('artifact', ['vectors.json','index.json','search.json','report.json','report.md'])
def test_tampering_is_rejected_even_after_receipt_artifact_rehash(tmp_path, artifact):
    from rag_quality_bench.models import canonical_sha256
    model,payload=vector_fixture();out=tmp_path/'workflow'
    receipt=run_workflow(model,vectors=payload,query='launch café a',output=out,minimum_pass_rate=0)
    path=out/artifact
    if artifact=='report.md': path.write_bytes(path.read_bytes()+b'changed')
    else:
        value=json.loads(path.read_bytes())
        if artifact=='vectors.json':value['chunks'][0]['vector']=[1,0]
        elif artifact=='index.json':value['vectors']['model_version']='forged'
        elif artifact=='search.json':value['hits'][0]['quote']='forged'
        else:value['records'][0]['retrieved'][0]['vector_score']=.123
        path.write_text(json.dumps(value),encoding='utf-8')
    receipt['artifacts'][artifact]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
    receipt['receipt_sha256']=canonical_sha256({k:v for k,v in receipt.items() if k!='receipt_sha256'})
    (out/'workflow.json').write_text(json.dumps(receipt),encoding='utf-8')
    with pytest.raises(ContractError):verify_workflow(out,model,vectors=payload)


def test_different_explicit_vectors_refused_against_unchanged_workflow(tmp_path):
    model,payload=vector_fixture();out=tmp_path/'workflow'
    run_workflow(model,vectors=payload,query='launch café a',output=out,minimum_pass_rate=0)
    payload['chunks'][0]['vector']=[1,0]
    with pytest.raises(ContractError,match='vectors replay mismatch'):verify_workflow(out,model,vectors=payload)


def test_cli_workflow_index_run_export_and_replay_use_real_engine(tmp_path,capsys):
    from rag_quality_bench.cli import main
    model,payload=vector_fixture(); suite_path=tmp_path/'suite.json';vectors_path=tmp_path/'input-vectors.json'
    suite_path.write_text(json.dumps(model.to_dict()),encoding='utf-8');vectors_path.write_text(json.dumps(payload),encoding='utf-8')
    common=['--suite',str(suite_path),'--vectors',str(vectors_path)]
    out=tmp_path/'workflow'
    assert main(['workflow',*common,'--query','launch café a','--output',str(out),'--minimum-pass-rate','0'])==0
    assert json.loads(capsys.readouterr().out)['schema_version']=='rag-lab/workflow-v3'
    assert main(['verify-workflow',*common,'--output',str(out)])==0
    assert json.loads(capsys.readouterr().out)['valid'] is True
    assert main(['index',*common,'--output',str(tmp_path/'index.json')])==0
    assert json.loads(capsys.readouterr().out)['index_version']=='2.0'
    report=tmp_path/'run.json'
    assert main(['run',*common,'--output',str(report)])==0
    assert json.loads(capsys.readouterr().out)['metrics']['retrieval_strategy']=='supplied'
    for kind in ['markdown','html']:
        path=tmp_path/('export.'+kind)
        assert main(['export','--report',str(report),'--format',kind,'--output',str(path)])==0
        assert path.stat().st_size>0;capsys.readouterr()
    assert main(['workflow','--suite',str(suite_path),'--query','launch café a','--output',str(tmp_path/'missing')])==2
    assert not (tmp_path/'missing').exists()


def test_index_metadata_has_truthful_limits_and_tamper_detection():
    from rag_quality_bench.retrieval import verify_manifest
    from rag_quality_bench.models import canonical_sha256
    model,payload=vector_fixture();manifest=BenchmarkEngine(model,vectors=payload).index_manifest()
    assert verify_manifest(manifest)
    for field,value in [('origin_verified',True),('provider_called',True),('dimension',True)]:
        changed=deepcopy(manifest);changed['vectors'][field]=value
        changed['manifest_sha256']=canonical_sha256({k:v for k,v in changed.items() if k!='manifest_sha256'})
        assert not verify_manifest(changed)


def test_query_exact_bytes_and_token_bounds_never_fallback():
    model,payload=vector_fixture()
    engine=BenchmarkEngine(model,vectors=payload)
    for query in ['launch  café a', 'Launch café a']:
        with pytest.raises(ContractError,match='query vector'):engine.search(query)
    query='word '*1025;digest=content_sha256(query)
    payload['queries'].append({**payload['queries'][0],'id':digest,'text_sha256':digest})
    with pytest.raises(ContractError,match='token/byte bound'):BenchmarkEngine(model,vectors=payload).search(query)


def test_changed_or_blocked_corpus_cannot_reuse_previous_vectors():
    model,payload=vector_fixture()
    changed=replace(model,documents=(replace(model.documents[0],trust='blocked'),model.documents[1]))
    payload['suite_sha256']=changed.digest
    with pytest.raises(ContractError,match='chunk IDs/text hashes'):BenchmarkEngine(changed,vectors=payload)


def test_overflow_rejection_is_an_explicit_strengthening_of_source_doctor():
    doctor=source_engine('semantic-index-doctor','semantic_index_doctor')
    # The old norm check only tests zero; it accepts an infinite norm formed
    # from individually finite components. The new boundary must refuse it.
    vector=[1.7e308,1.7e308]
    assert doctor.diagnose([{'id':'chunk','vector':vector}],expected_dimension=2)['status']=='healthy'
    model,payload=vector_fixture();payload['chunks'][0]['vector']=vector
    with pytest.raises(ContractError,match='norm overflow'):BenchmarkEngine(model,vectors=payload)


def test_forged_validated_snapshot_is_bounded_before_decode(monkeypatch):
    import rag_quality_bench.supplied_vectors as module
    model,payload=vector_fixture();validated=BenchmarkEngine(model,vectors=payload).vectors
    monkeypatch.setattr(module,'MAX_VECTOR_BYTES',1)
    with pytest.raises(ContractError,match='byte bound'):BenchmarkEngine(model,vectors=validated)


def test_canonical_namespace_and_public_example_execute(tmp_path):
    import rag_lab
    root=Path(__file__).resolve().parents[1]
    model=rag_lab.BenchmarkSuite.from_json((root/'examples/supplied-suite.json').read_text(encoding='utf-8'))
    payload=rag_lab.load_vectors(root/'examples/supplied-vectors.json')
    assert rag_lab.SuppliedVectors is type(BenchmarkEngine(model,vectors=payload).vectors)
    out=tmp_path/'example'
    receipt=rag_lab.run_workflow(model,vectors=payload,query='launch café a',minimum_pass_rate=0,output=out)
    assert rag_lab.verify_workflow(out,model,vectors=payload)==receipt
    search=json.loads((out/'search.json').read_bytes())
    originals={d.source_id:d.content for d in model.documents}
    for hit in search['hits']:
        assert originals[hit['source_id']][hit['char_start']:hit['char_end']]==hit['quote']
    from rag_quality_bench.reporting import render_html, render_markdown
    report=json.loads((out/'report.json').read_bytes())
    assert 'origin is not verified' in render_html(report)
    assert 'origin is not verified' in render_markdown(report)


def test_low_level_index_cannot_relabel_vector_suite():
    from rag_quality_bench.retrieval import RetrievalIndex, RetrievalError
    model,payload=vector_fixture();engine=BenchmarkEngine(model,vectors=payload)
    chunks=engine._index({d.source_id:d for d in model.documents})
    index=RetrievalIndex(chunks,strategy='supplied',vectors=engine.vectors)
    with pytest.raises(RetrievalError,match='suite identity'):
        index.manifest(suite_sha256='0'*64,chunk_size=model.chunk_size,chunk_overlap=model.chunk_overlap)
