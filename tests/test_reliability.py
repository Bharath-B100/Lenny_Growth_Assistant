import pytest
from backend import agent, retrieval
from backend.safety import citation_ids, word_count

SOURCES=[{'id':'S1','title':'Retention','guest':'Guest','text':'Measure retention by cohort.'}]

@pytest.mark.parametrize('question,expected',[
    ('Explain retention','answer'),('Write a Ship30 essay','essay'),
    ('Create an HTML page','html'),('Create a markdown checklist','markdown')])
def test_routing(question,expected):
    assert agent.route(question)==expected
    assert agent.route(question,'answer')=='answer'

def test_direct_html_is_complete_sanitized_and_grounded(monkeypatch):
    outputs=iter(['<main><h1>Retention</h1><p>Measure cohorts. [S1]</p><script>alert(1)</script></main>','SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    _,art,meta=agent.run_task('Make HTML',[],SOURCES,'ollama','html',lambda _:None)
    assert '<!doctype html>' in art['content'] and '<style>' in art['content']
    assert '<script>' not in art['content'] and art['word_count']==3
    assert meta['grounding']=='cited'

def test_incomplete_html_repaired_once(monkeypatch):
    outputs=iter(['<main><h1>Retention','<main><h1>Retention</h1><p>Cohorts [S1]</p></main>','SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    assert agent.run_task('HTML',[],SOURCES,'ollama','html',lambda _:None)[1]

@pytest.mark.parametrize('mode,draft,repair',[
    ('markdown','# Retention\nAn unsupported claim [S1].', '# Retention\nMeasure retention by cohort [S1].'),
    ('html','<main><h1>Retention</h1><p>An unsupported claim [S1].</p></main>', '<main><h1>Retention</h1><p>Measure retention by cohort [S1].</p></main>'),
])
def test_unverified_artifact_gets_one_rewrite_and_final_review(monkeypatch,mode,draft,repair):
    outputs=iter([draft,'UNSUPPORTED: This claim is not in the excerpt.',repair,'SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    answer,artifact,meta=agent.run_task('Create a document',[],SOURCES,'ollama',mode,lambda _:None)
    assert artifact and meta['grounding']=='cited' and meta['cited_ids']==['S1']
    assert 'Measure retention by cohort' in artifact['content']
    assert 'unsupported claim' not in artifact['content']
    if mode=='html':
        assert '<main>' in artifact['content'] and '<script>' not in artifact['content']

def test_markdown_artifact_gets_second_bounded_repair(monkeypatch):
    outputs=iter([
        '# Retention\nUnsupported claim [S1].',
        'UNSUPPORTED: This claim is not in the excerpt.',
        '# Retention\nFirst rewrite [S1].',
        'UNSUPPORTED: The practical conclusion is not supported.',
        '# Retention\nMeasure retention by cohort [S1].',
        'SUPPORTED',
    ])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    _,artifact,meta=agent.run_task('Create a document',[],SOURCES,'ollama','markdown',lambda _:None)
    assert artifact and 'Measure retention by cohort' in artifact['content']
    assert meta['grounding']=='cited'

def test_invalid_html_is_never_saved(monkeypatch):
    monkeypatch.setattr(agent,'generate',lambda *a,**k:'<main>unfinished [S1]')
    with pytest.raises(agent.GenerationError) as exc:
        agent.run_task('HTML',[],SOURCES,'ollama','html',lambda _:None)
    assert exc.value.code=='INVALID_HTML'

def test_unsupported_evidence_abstains_without_artifact(monkeypatch):
    monkeypatch.setattr(agent,'generate',lambda *a,**k:'INSUFFICIENT_EVIDENCE')
    answer,art,meta=agent.run_task('HTML about tomorrow',[],SOURCES,'ollama','html',lambda _:None)
    assert answer==agent.ABSTAIN and art is None and meta['grounding']=='insufficient'

def test_grouped_citations_are_not_counted_as_words():
    assert citation_ids('Fact [S1, S2] and [S3]')=={'S1','S2','S3'}
    assert word_count('Fact [S1, S2] and [S3]')==2

def test_followup_retrieval_inherits_topic_and_diversifies(monkeypatch):
    captured=[]
    def query(sql,args):
        captured.append(args)
        return [dict(chunk_id=str(i),episode_id='a' if i<3 else 'b',text='retention cohorts improve',title='Retention',guest='Guest Name',rank=5-i) for i in range(4)]
    monkeypatch.setattr(retrieval.db,'all_rows',query)
    sources=retrieval.retrieve('Turn this into HTML','Explain retention cohorts')
    assert 'retention' in captured[0][0] and len(sources)==3
    assert [s['id'] for s in sources]==['S1','S2','S3']

def test_named_guest_retrieval_keeps_more_relevant_passages(monkeypatch):
    rows=[dict(chunk_id=str(i),episode_id='teresa',text='continuous discovery user interviews weekly',
               title='Discovery',guest='Teresa Torres',rank=6-i/10) for i in range(5)]
    rows.append(dict(chunk_id='other',episode_id='other',text='continuous discovery user interviews weekly',
                     title='Other',guest='Other Guest',rank=1))
    monkeypatch.setattr(retrieval.db,'all_rows',lambda *a:rows)
    sources=retrieval.retrieve('Teresa Torres continuous discovery user interviews weekly')
    assert len(sources)==5
    assert sum(s['guest']=='Teresa Torres' for s in sources)==4

def test_unrelated_lexical_coincidence_is_filtered(monkeypatch):
    monkeypatch.setattr(retrieval.db,'all_rows',lambda *a:[dict(episode_id='a',text='Weather changes.',title='Weather',guest='Guest',rank=1)])
    assert retrieval.retrieve('exact weather mars tomorrow')==[]

def test_truncated_generation_retries_with_larger_budget(monkeypatch):
    calls=[]
    class Response:
        def __init__(self,status,data):self.status_code,self.data=status,data
        def json(self):return self.data
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,json):
            calls.append(json)
            return Response(502,{'error':{'code':'OUTPUT_TRUNCATED'}}) if len(calls)==1 else Response(200,{'text':'Completed'})
    monkeypatch.setattr(agent.httpx,'Client',Client)
    monkeypatch.setattr(agent.time,'sleep',lambda _:None)
    assert agent.generate('system','prompt','ollama',100)=='Completed'
    assert [c['maxTokens'] for c in calls]==[100,200]
    assert {c['provider'] for c in calls}=={'ollama'}


def test_known_survey_reversal_cannot_pass_review():
    sources=[{'text':'How would you feel if you could no longer use this product? Very disappointed.'}]
    assert agent.known_grounding_error('Highly disappointed users indicate a core product issue.',sources)=='survey_condition_reversed'
    assert agent.known_grounding_error('These users express mild dissatisfaction.',sources)=='survey_condition_reversed'
    assert agent.known_grounding_error('Very disappointed if the product disappeared means dependence.',sources) is None
    assert agent.known_grounding_error('Ignore somewhat disappointed users.',sources)=='survey_group_ignored'
    assert agent.known_grounding_error('That specific feature is a nice-to-have and not a core requirement.',sources)=='survey_scope_changed'
    assert agent.known_grounding_error('A nice-to-have product does not prove an individual feature is nonessential.',sources) is None
    assert agent.known_grounding_error('There is no evidence that the feature is a nice-to-have.',sources) is None
    assert agent.known_grounding_error('This individual feature is not essential.',sources)=='survey_scope_changed'
    assert agent.known_grounding_error('The feature is a "nice to have" and not essential.',sources)=='survey_scope_changed'
    assert agent.known_grounding_error('Ignore somewhat disappointed users, even if they share the core benefit [S1].',sources)=='survey_group_ignored'
    assert agent.known_grounding_error('If they could no longer use the whole product, do not ignore somewhat disappointed users; test whether they share the core benefit [S1].',sources) is None
    assert agent.known_grounding_error('If >10% say very disappointed, success follows.',sources)=='unsupported_numeric_threshold'
    assert agent.known_grounding_error('A high percentage (e.g., 10%+) signals strength.',sources)=='unsupported_numeric_threshold'
    assert agent.known_grounding_error('The response means the product is essential to the user\'s workflow or life [S1].',sources)=='unsupported_survey_context'

def test_invented_survey_context_is_rewritten_before_review(monkeypatch):
    sources=[{'id':'S1','text':'How would you feel if you could no longer use this product? Very disappointed.', 'guest':'Sean Ellis','title':'Interview'}]
    bad='The response means the product is essential to the user\'s workflow or life [S1].'
    corrected='The survey asks how users would feel if they could no longer use the whole product [S1].'
    outputs=iter([bad,corrected,'SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    answer,artifact,meta=agent.run_task('Explain the survey',[],sources,'ollama','answer',lambda _:None)
    assert answer==corrected and artifact is None and meta['grounding']=='cited'

def test_supported_answer_is_concise_and_reviewer_flag_gets_one_repair(monkeypatch):
    outputs=iter([
        'Teams should measure retention by cohort and adjust the product strategy [S1].',
        'UNSUPPORTED: The strategy adjustment is not stated in the excerpt.',
        '- Measure retention by cohort. [S1]',
        'SUPPORTED',
    ])
    prompts=[]
    def fake(system,prompt,provider,tokens):
        prompts.append((prompt,tokens))
        return next(outputs)
    monkeypatch.setattr(agent,'generate',fake)
    answer,artifact,meta=agent.run_task('Explain retention',[],SOURCES,'ollama','answer',lambda _:None)
    assert answer=='- Measure retention by cohort. [S1]'
    assert artifact is None and meta['grounding']=='cited' and meta['cited_ids']==['S1']
    assert 'no more than 150 words' in prompts[0][0]
    assert 'The strategy adjustment is not stated' in prompts[2][0]

def test_answer_without_citations_gets_one_citation_repair(monkeypatch):
    outputs=iter(['Measure retention by cohort.','- Measure retention by cohort. [S1]','SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    answer,artifact,meta=agent.run_task('Explain retention',[],SOURCES,'ollama','answer',lambda _:None)
    assert answer=='- Measure retention by cohort. [S1]'
    assert artifact is None and meta['grounding']=='cited'

def test_default_answer_is_condensed_and_never_returns_oversized_output(monkeypatch):
    long_draft=' '.join(['unsupported']*220)+' [S1]'
    outputs=iter([long_draft,'- Measure retention by cohort. [S1]','SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    answer,_,meta=agent.run_task('Explain retention',[],SOURCES,'ollama','answer',lambda _:None)
    assert answer=='- Measure retention by cohort. [S1]'
    assert agent.word_count(answer)<=agent.MAX_DEFAULT_ANSWER_WORDS and meta['grounding']=='cited'

def test_survey_feature_scope_error_is_rewritten_before_review(monkeypatch):
    sources=[{'id':'S1','text':'How would you feel if you could no longer use this product? Very disappointed.', 'guest':'Sean Ellis','title':'Interview'}]
    bad='Somewhat disappointed product users mean the feature is a "nice to have" and is not essential [S1].'
    corrected='The survey asks whether users would be disappointed if they could no longer use the whole product [S1]. This measures dependence, not current dissatisfaction, and does not prove an individual feature is nonessential [S1].'
    outputs=iter([bad,corrected,'SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    answer,artifact,meta=agent.run_task('Explain the survey',[],sources,'ollama','answer',lambda _:None)
    assert answer==corrected and artifact is None and meta['grounding']=='cited'

def test_advice_to_ignore_survey_group_is_corrected_before_review(monkeypatch):
    sources=[{'id':'S1','text':'How would you feel if you could no longer use this product? Somewhat disappointed. On-the-fence users who share the must-have users’ core benefit could be moved up without breaking that benefit.', 'guest':'Sean Ellis','title':'Interview'}]
    bad='The survey asks how users would feel if they could no longer use the product. Ignore somewhat disappointed users [S1].'
    corrected='The survey asks how users would feel if they could no longer use the whole product [S1]. Do not ignore somewhat disappointed users; assess whether they share the core benefit and how to move them toward it without breaking that benefit [S1].'
    outputs=iter([bad,corrected,'SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    answer,artifact,meta=agent.run_task('Explain the survey',[],sources,'ollama','answer',lambda _:None)
    assert answer==corrected and artifact is None and meta['grounding']=='cited'

def test_persistent_scope_claim_is_removed_before_artifact_review(monkeypatch):
    sources=[{'id':'S1','text':'How would you feel if you could no longer use this product? Very disappointed.', 'guest':'Sean Ellis','title':'Interview'}]
    bad='# Survey\n- The feature is a nice-to-have and not essential [S1].'
    still_bad=bad+'\n- The whole-product result does not establish feature-level criticality [S1].'
    outputs=iter([bad,still_bad,still_bad,'SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    _,artifact,meta=agent.run_task('Create a Markdown brief',[],sources,'ollama','markdown',lambda _:None)
    assert artifact and 'whole-product result' in artifact['content']
    assert 'feature is a nice-to-have' not in artifact['content'] and meta['grounding']=='cited'

def test_scope_claim_removal_preserves_safe_html_paragraphs():
    sources=[{'id':'S1','text':'How would you feel if you could no longer use this product? Very disappointed.'}]
    raw='<main><h1>Survey</h1><ul><li>The feature is a nice-to-have and not essential [S1].</li><li>The whole-product result does not establish feature-level criticality [S1].</li></ul></main>'
    cleaned=agent.remove_scope_claim_blocks('html',raw,sources)
    assert 'The feature is a nice-to-have' not in cleaned
    assert 'whole-product result' in cleaned

def test_markdown_removes_group_rejection_but_keeps_supported_guidance():
    sources=[{'text':'How would you feel if you could no longer use this product? Somewhat disappointed.'}]
    cleaned=agent.remove_scope_claim_blocks('markdown','- Ignore somewhat disappointed users [S1].\n- Test their shared core benefit [S1].',sources)
    assert 'Ignore somewhat disappointed' not in cleaned and 'Test their shared core benefit' in cleaned

def test_empty_markdown_list_heading_is_removed_without_dropping_content():
    text='- **Filtering Feedback**:  \n\n- **Practical Application**:  \n  Focus on whole-product value [S1].'
    cleaned=agent.clean_empty_markdown_list_headers(text)
    assert 'Filtering Feedback' not in cleaned
    assert 'Practical Application' in cleaned and 'Focus on whole-product value [S1]' in cleaned

def test_reviewer_parser_requires_clear_affirmative_status():
    assert agent.reviewer_approved('SUPPORTED')
    assert agent.reviewer_approved('**SUPPORTED**\nAll claims match the excerpts.')
    assert agent.reviewer_approved('SUPPORTED\nNo unsupported claims were found.')
    assert not agent.reviewer_approved('SUPPORTED, but one claim is unsupported.')
    assert not agent.reviewer_approved('The draft appears supported.')
    assert not agent.reviewer_approved('UNSUPPORTED: One claim is missing evidence.')

def test_persistent_survey_scope_error_gets_one_more_specific_correction(monkeypatch):
    sources=[{'id':'S1','text':'How would you feel if you could no longer use this product? Very disappointed.', 'guest':'Sean Ellis','title':'Interview'}]
    first='If you could no longer use the whole product, some users are somewhat disappointed; this proves a feature is nonessential [S1].'
    still_bad='The question is whether you could no longer use the whole product; the feature is nice-to-have [S1].'
    corrected='The survey asks how users would feel if they could no longer use the whole product [S1]. That result does not establish whether any particular feature is essential [S1].'
    outputs=iter([first,still_bad,corrected,'SUPPORTED'])
    prompts=[]
    def fake(system,prompt,provider,tokens):
        prompts.append(prompt)
        return next(outputs)
    monkeypatch.setattr(agent,'generate',fake)
    answer,artifact,meta=agent.run_task('Explain the survey',[],sources,'ollama','answer',lambda _:None)
    assert answer==corrected and artifact is None and meta['grounding']=='cited'
    assert 'Do not label any particular feature' in prompts[2]

def test_answer_still_overlong_after_rewrite_is_withheld(monkeypatch):
    long_draft=' '.join(['unsupported']*220)+' [S1]'
    outputs=iter([long_draft,long_draft])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    answer,artifact,meta=agent.run_task('Explain retention',[],SOURCES,'ollama','answer',lambda _:None)
    assert 'withheld' in answer and artifact is None and meta['grounding']=='rejected'

def test_unverified_essay_section_gets_one_repair_and_must_pass_review(monkeypatch):
    outputs=iter(['UNSUPPORTED: This claim turns a hypothetical survey example into a general rule.',
                  '## Evidence-backed section\nThe product survey measures dependence [S1].',
                  'SUPPORTED'])
    prompts=[]
    def fake(system,prompt,provider,tokens):
        prompts.append(prompt)
        return next(outputs)
    monkeypatch.setattr(agent,'generate',fake)
    revised,ok=agent.review_block('## Evidence-backed section\nA universal rule [S1].','strict reviewer','writer',SOURCES,'ollama')
    assert ok and 'measures dependence' in revised
    assert len(prompts)==3 and 'hypothetical survey example' in prompts[1]

def test_unverified_essay_section_without_valid_citation_stays_rejected(monkeypatch):
    outputs=iter(['UNSUPPORTED: The premise is not in the excerpt.','## Section\nUnsupported rewrite.',
                  '## Section\nStill missing citations.'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    revised,ok=agent.review_block('## Section\nUnsupported claim [S1].','reviewer','writer',SOURCES,'ollama')
    assert not ok and revised=='## Section\nStill missing citations.'

def test_essay_section_repairs_deterministic_survey_group_error(monkeypatch):
    source=[{'id':'S1','title':'Interview','guest':'Sean Ellis','text':'How would you feel if you could no longer use this product? Somewhat disappointed users sharing the core benefit can be moved toward must-have without breaking that benefit.'}]
    bad='## Section\nIf users would be disappointed if they could no longer use the whole product, ignore somewhat disappointed users [S1].'
    corrected='## Section\nThe survey measures how users would feel if they could no longer use the whole product [S1]. Do not ignore somewhat disappointed users; assess whether they share the core benefit and how to move them toward it without breaking that benefit [S1].'
    outputs=iter([corrected,'SUPPORTED'])
    prompts=[]
    def fake(system,prompt,provider,tokens):
        prompts.append(prompt)
        return next(outputs)
    monkeypatch.setattr(agent,'generate',fake)
    revised,ok=agent.review_block(bad,'reviewer','writer',source,'ollama')
    assert ok and revised==corrected
    assert 'Do not recommend ignoring' in prompts[0]

def test_essay_section_gets_second_bounded_repair_and_final_review(monkeypatch):
    outputs=iter([
        'UNSUPPORTED: The first draft states an unsupported rule.',
        '## Section\nA narrower claim is supported [S1].',
        'UNSUPPORTED: The suggestion is not clearly labelled.',
        '## Section\nThe transcript says measure cohorts [S1]. Suggested application: review them weekly.',
        'SUPPORTED',
    ])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    revised,ok=agent.review_block('## Section\nAn unsupported universal rule [S1].','reviewer','writer',SOURCES,'ollama')
    assert ok and 'Suggested application' in revised

def test_conflicting_metadata_does_not_offer_wrong_video():
    from scripts.ingest import source_metadata
    title,guest,video=source_metadata({'title':'Word of mouth | Nilan Peiris','guest':'Alexander Embiricos','youtube_url':'https://youtube.com/wrong'},'alexander-embiricos')
    assert 'mismatch' in title and guest=='Alexander Embiricos' and not video

def test_known_guest_spelling_error_is_corrected_for_retrieval():
    from scripts.ingest import source_metadata
    title,guest,video=source_metadata({'title':'NYT product | Alex Hardiman','guest':'Alex Hardimen','youtube_url':'https://youtube.com/right'},'alex-hardimen')
    assert guest=='Alex Hardiman' and 'Alex Hardiman' in title and video.endswith('right')


def test_numeric_hallucination_is_revised_before_saving(monkeypatch):
    sources=[{'id':'S1','text':'How would you feel if you could no longer use this product? Very disappointed.', 'guest':'Sean Ellis','title':'Interview'}]
    outputs=iter(['If 10%+ say very disappointed, success follows [S1].',
                  'Survey users about losing access to the product [S1].','SUPPORTED'])
    monkeypatch.setattr(agent,'generate',lambda *a,**k:next(outputs))
    answer,artifact,meta=agent.run_task('Create a checklist',[],sources,'ollama','markdown',lambda _:None)
    assert artifact and '10%' not in artifact['content'] and meta['grounding']=='cited'
