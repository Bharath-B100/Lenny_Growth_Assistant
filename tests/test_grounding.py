from backend import agent


def evidence():
    return [{'id':'S1','title':'Retention','guest':'Guest','text':'Measure retention by cohort.'}]


def test_empty_retrieval_never_calls_model(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Unsupported request must not call the model')
    monkeypatch.setattr(agent, 'generate', forbidden)
    answer, artifact, meta = agent.run_task('Predict tomorrow', [], [], 'ollama', 'answer', lambda _: None)
    assert answer == agent.ABSTAIN
    assert artifact is None
    assert meta['grounding'] == 'insufficient'


def test_unknown_citation_cannot_become_downloadable_artifact(monkeypatch):
    monkeypatch.setattr(agent, 'generate', lambda *a, **k: '# Fabricated claim [S99]')
    _, artifact, meta = agent.run_task('Create a checklist', [], evidence(), 'ollama', 'markdown', lambda _: None)
    assert artifact is None
    assert meta['grounding'] == 'rejected'


def test_cited_markdown_keeps_source_metadata(monkeypatch):
    outputs=iter(['# Retention\nMeasure retention by cohort. [S1]', 'SUPPORTED'])
    monkeypatch.setattr(agent, 'generate', lambda *a, **k: next(outputs))
    _, artifact, meta = agent.run_task('Create a checklist', [], evidence(), 'ollama', 'markdown', lambda _: None)
    assert artifact['kind'] == 'markdown'
    assert meta['cited_ids'] == ['S1']
    assert meta['provider'] == 'ollama'


def test_timeout_does_not_switch_provider(monkeypatch):
    calls=[]
    def failed(system,prompt,provider,*args):
        calls.append(provider)
        raise agent.GenerationError('MODEL_TIMEOUT','Timed out')
    monkeypatch.setattr(agent,'generate',failed)
    import pytest
    with pytest.raises(agent.GenerationError,match='Timed out'):
        agent.run_task('Explain retention',[],evidence(),'ollama','answer',lambda _:None)
    assert calls == ['ollama']


def test_evidence_review_rejects_claim_even_with_valid_citation(monkeypatch):
    outputs=iter(['Claim reverses the evidence. [S1]','UNSUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    _,artifact,meta=agent.run_task('Write a checklist',[],evidence(),'ollama','markdown',lambda _:None)
    assert artifact is None
    assert meta['grounding']=='rejected'
