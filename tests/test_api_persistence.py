"""Real PostgreSQL in a unique temporary schema; no provider requests or user-data changes.
Run with LENNY_INTEGRATION=1 against the configured local database.
"""
import os
import uuid
import pytest
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from fastapi.testclient import TestClient
from backend import main, db
from backend.config import DATABASE_URL

pytestmark=pytest.mark.skipif(os.getenv('LENNY_INTEGRATION')!='1',reason='Set LENNY_INTEGRATION=1 for isolated real PostgreSQL checks')

@pytest.fixture
def api(monkeypatch):
    schema='test_lenny_'+uuid.uuid4().hex
    with psycopg.connect(DATABASE_URL,autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    pool=ConnectionPool(DATABASE_URL,min_size=0,max_size=3,kwargs={'row_factory':dict_row,'options':'-c search_path='+schema},open=False)
    monkeypatch.setattr(db,'pool',pool)
    queued=[]
    class Queue:
        def submit(self,*args):queued.append(args)
    monkeypatch.setattr(main,'executor',Queue())
    try:
        db.initialize()
        client=TestClient(main.app)
        yield client,queued,schema
        client.close()
    finally:
        pool.close()
        with psycopg.connect(DATABASE_URL,autocommit=True) as admin:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

def session(client,uid):
    r=client.post('/api/sessions',json={'user_id':uid,'display_name':'Acceptance fixture'})
    assert r.status_code==201
    return r.json()['id']

def test_api_validation_isolation_and_durable_metadata(api):
    client,_,schema=api
    uid,foreign=str(uuid.uuid4()),str(uuid.uuid4())
    first,second=session(client,uid),session(client,uid)
    assert client.get(f'/api/sessions/{first}?user_id={foreign}').status_code==404
    assert client.post(f'/api/sessions/{first}/messages',json={'user_id':uid,'message':'   '}).status_code==422
    assert client.post('/api/sessions',headers={'Origin':'https://evil.invalid'},json={'user_id':uid}).status_code==403
    client.post(f'/api/sessions/{first}/messages',json={'user_id':uid,'message':'Explain retention','provider':'ollama'})
    assert len(client.get(f'/api/sessions/{first}?user_id={uid}').json()['messages'])==1
    assert client.get(f'/api/sessions/{second}?user_id={uid}').json()['messages']==[]
    with psycopg.connect(DATABASE_URL,options='-c search_path='+schema,row_factory=dict_row) as independent:
        assert independent.execute('SELECT count(*) AS n FROM messages').fetchone()['n']==1
        user=independent.execute('SELECT * FROM users').fetchone()
        assert user['metadata']['deployment']=='local' and user['created_at']

def test_artifact_job_persistence_conversion_and_preview_policy(api,monkeypatch):
    client,queued,_=api;uid=str(uuid.uuid4());sid=session(client,uid)
    monkeypatch.setattr(main,'retrieve',lambda *a:[])
    monkeypatch.setattr(main,'run_task',lambda *a:('Ready',{'kind':'markdown','content':'# Retention\nUse cohorts [S1]','title':'Retention','word_count':3},{'grounding':'cited'}))
    r=client.post(f'/api/sessions/{sid}/messages',json={'user_id':uid,'message':'Create a document'})
    assert r.status_code==202
    assert client.post(f'/api/sessions/{sid}/messages',json={'user_id':uid,'message':'Duplicate'}).status_code==409
    fn,*args=queued.pop();fn(*args)
    detail=client.get(f'/api/sessions/{sid}?user_id={uid}').json()
    assert len(detail['messages'])==2 and detail['last_job']['status']=='done'
    aid=detail['artifacts'][0]['id']
    assert client.get(f'/api/artifacts/{aid}?user_id={uuid.uuid4()}').status_code==404
    converted=client.post(f'/api/artifacts/{aid}/html?user_id={uid}').json()['id']
    preview=client.get(f'/api/artifacts/{converted}/preview?user_id={uid}')
    assert 'sandbox' in preview.headers['content-security-policy'] and 'Retention' in preview.text
    assert client.delete(f'/api/sessions/{sid}?user_id={uid}').status_code==200
    assert client.get(f'/api/artifacts/{aid}?user_id={uid}').status_code==404

def test_cancel_is_not_overwritten_by_model_failure(api,monkeypatch):
    client,queued,_=api;uid=str(uuid.uuid4());sid=session(client,uid)
    jid=client.post(f'/api/sessions/{sid}/messages',json={'user_id':uid,'message':'Explain retention'}).json()['job_id']
    monkeypatch.setattr(main,'retrieve',lambda *a:[])
    def failing(*args):
        client.post(f'/api/jobs/{jid}/cancel?user_id={uid}')
        raise main.GenerationError('MODEL_TIMEOUT','Timed out')
    monkeypatch.setattr(main,'run_task',failing)
    fn,*args=queued.pop();fn(*args)
    assert client.get(f'/api/jobs/{jid}?user_id={uid}').json()['status']=='cancelled'
    assert len(client.get(f'/api/sessions/{sid}?user_id={uid}').json()['messages'])==1

def test_restart_marks_unfinished_jobs_recoverable(api):
    client,_,_=api;uid=str(uuid.uuid4());sid=session(client,uid)
    jid=client.post(f'/api/sessions/{sid}/messages',json={'user_id':uid,'message':'Explain retention'}).json()['job_id']
    db.initialize(recover_jobs=True)
    job=client.get(f'/api/jobs/{jid}?user_id={uid}').json()
    assert job['status']=='error' and job['error_code']=='SERVER_RESTARTED'
    assert len(client.get(f'/api/sessions/{sid}?user_id={uid}').json()['messages'])==1


def test_saved_insights_download_and_docs(api,monkeypatch):
    client,queued,_=api;uid=str(uuid.uuid4());sid=session(client,uid)
    monkeypatch.setattr(main,'retrieve',lambda *a:[])
    monkeypatch.setattr(main,'run_task',lambda *a:('Saved evidence',{'kind':'markdown','content':'# Evidence','title':'Evidence','word_count':1},{'grounding':'cited'}))
    client.post(f'/api/sessions/{sid}/messages',json={'user_id':uid,'message':'Write a document','audience':'Founders'})
    fn,*args=queued.pop();fn(*args)
    detail=client.get(f'/api/sessions/{sid}?user_id={uid}').json();mid=detail['last_job']['id']
    message=next(m for m in detail['messages'] if m['role']=='assistant')['id']
    assert client.patch(f'/api/messages/{message}/saved',json={'user_id':uid,'saved':True}).status_code==200
    assert len(client.get(f'/api/insights?user_id={uid}').json()['insights'])==1
    assert client.patch(f'/api/messages/{message}/saved',json={'user_id':str(uuid.uuid4()),'saved':False}).status_code==404
    aid=detail['artifacts'][0]['id'];response=client.get(f'/api/artifacts/{aid}/download?user_id={uid}')
    assert response.text=='# Evidence' and 'attachment' in response.headers['content-disposition']
    assert client.get(f'/api/artifacts/{aid}/download?user_id={uuid.uuid4()}').status_code==404
    docs=client.get('/docs');assert docs.status_code==200 and '/api/insights' in docs.text and '<script' not in docs.text
