import json
import re
import html
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal

import httpx
import psycopg
from psycopg.types.json import Jsonb
from psycopg_pool import PoolTimeout
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .config import ROOT, OLLAMA_URL, OLLAMA_MODEL, GEMINI_MODEL, BRIDGE_URL, DEFAULT_PROVIDER
from .agent import route, run_task, GenerationError
from .retrieval import retrieve
from .safety import markdown_html, sanitize_html, word_count, CSP

class LogFormatter(logging.Formatter):
    def format(self,record):
        return json.dumps({'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'level':record.levelname,'event':record.getMessage(),**getattr(record,'event_data',{})})

handler=logging.StreamHandler()
handler.setFormatter(LogFormatter())
log=logging.getLogger('lenny'); log.setLevel(logging.INFO); log.handlers=[handler]
executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='lenny-agent')

@asynccontextmanager
async def lifespan(app):
    try:
        db.initialize(recover_jobs=True)
        app.state.ready=True
    except Exception as e:
        app.state.ready=False
        log.error('database_startup_failed',extra={'event_data':{'type':type(e).__name__}})
    yield
    executor.shutdown(wait=False,cancel_futures=True)
    db.pool.close()

app=FastAPI(title='The Lenny Growth Assistant',version='1.0.0',lifespan=lifespan,docs_url=None,redoc_url=None)
app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')

@app.middleware('http')
async def safety_headers(request:Request,call_next):
    request_id=str(uuid.uuid4())
    request.state.request_id=request_id
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin!=str(request.base_url).rstrip('/'):
        return JSONResponse({'error':{'code':'ORIGIN_REJECTED','message':'Requests must originate from this application.','request_id':request_id}},403)
    start=time.monotonic()
    response=await call_next(request)
    response.headers['X-Request-ID']=request_id
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api') else 'no-cache'
    if '/preview' not in request.url.path:
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    log.info('http_request',extra={'event_data':{'request_id':request_id,'method':request.method,'path':request.url.path,'status':response.status_code,'ms':round((time.monotonic()-start)*1000)}})
    return response

def error(request,code,message,status=500):
    return JSONResponse({'error':{'code':code,'message':message,'request_id':getattr(request.state,'request_id',None)}},status_code=status)

@app.exception_handler(HTTPException)
async def http_error(request,exc):
    detail=exc.detail if isinstance(exc.detail,dict) else {'code':'REQUEST_ERROR','message':str(exc.detail)}
    return error(request,detail.get('code','REQUEST_ERROR'),detail.get('message','Request failed'),exc.status_code)

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    return error(request,'VALIDATION_ERROR','Check the request fields. A message must contain 1–4,000 characters and valid session/user IDs.',422)

@app.exception_handler(PoolTimeout)
@app.exception_handler(psycopg.OperationalError)
async def database_error(request,exc):
    log.error('database_unavailable')
    return error(request,'DATABASE_UNAVAILABLE','The database is unavailable. Start the database service and restart the app.',503)

@app.exception_handler(Exception)
async def unknown_error(request,exc):
    log.error('unexpected_error',extra={'event_data':{'type':type(exc).__name__}})
    return error(request,'INTERNAL_ERROR','Something went wrong. See the request ID in server logs.',500)

class NewSession(BaseModel):
    user_id: uuid.UUID
    display_name:str=Field(default='Local researcher',min_length=1,max_length=80)

class ChatRequest(BaseModel):
    user_id:uuid.UUID
    message:str=Field(min_length=1,max_length=4000)
    mode:Literal['auto','answer','essay','markdown','html']='auto'
    provider:Literal['ollama','gemini']='ollama'
    audience:str=Field(default='Product and growth teams',max_length=160)

class RenameRequest(BaseModel):
    user_id:uuid.UUID
    title:str=Field(min_length=1,max_length=100)

def owned(session_id,user_id):
    row=db.one('SELECT * FROM sessions WHERE id=%s AND user_id=%s',(session_id,user_id))
    if not row: raise HTTPException(404,{'code':'SESSION_NOT_FOUND','message':'This conversation was not found.'})
    return row

@app.get('/')
def index(): return FileResponse(ROOT/'frontend'/'index.html')

@app.get('/health/live')
def live(): return {'status':'ok','service':'lenny-api'}

@app.get('/health/ready')
def ready():
    try: db.one('SELECT 1 AS ok')
    except Exception: return JSONResponse({'status':'degraded','database':False},503)
    return {'status':'ok','database':True}

@app.get('/api/status')
def status():
    stats={'episodes':0,'chunks':0}
    database=True
    try:
        stats=db.one('SELECT (SELECT count(*) FROM episodes) AS episodes,(SELECT count(*) FROM chunks) AS chunks')
    except Exception: database=False
    agent=False; gemini=False; ollama=False; models=[]; gemini_state="unverified"
    try:
        response=httpx.get(BRIDGE_URL+'/health',timeout=3); response.raise_for_status()
        info=response.json(); agent=True; gemini=info.get('geminiConfigured',False); gemini_state=info.get('geminiState','unverified')
    except Exception: pass
    try:
        response=httpx.get(OLLAMA_URL+'/api/tags',timeout=3);response.raise_for_status()
        models=[m['name'] for m in response.json().get('models',[])]
        ollama=OLLAMA_MODEL in models
    except Exception: pass
    return {'database':database,'agent':agent,'ollama':ollama,'gemini':gemini,'gemini_state':gemini_state,**stats,
            'providers':[{'id':'ollama','label':'Local Ollama','model':OLLAMA_MODEL,'ready':ollama and agent},{'id':'gemini','label':'Gemini Cloud','model':GEMINI_MODEL,'ready':gemini and agent and gemini_state not in ('authentication_failed','quota_exceeded'),'verification':gemini_state}],
            'default_provider':DEFAULT_PROVIDER,'local_only':True}

@app.post('/api/sessions',status_code=201)
def create_session(body:NewSession):
    sid=uuid.uuid4()
    with db.connection() as conn:
        conn.execute('INSERT INTO users(id,display_name,metadata) VALUES(%s,%s,%s) ON CONFLICT(id) DO NOTHING',(body.user_id,body.display_name,Jsonb({'deployment':'local','auth':'single-user'})))
        row=conn.execute('INSERT INTO sessions(id,user_id) VALUES(%s,%s) RETURNING *',(sid,body.user_id)).fetchone()
    return row

@app.get('/api/sessions')
def sessions(user_id:uuid.UUID):
    return {'sessions':db.all_rows('SELECT * FROM sessions WHERE user_id=%s ORDER BY updated_at DESC LIMIT 100',(user_id,))}

@app.get('/api/sessions/{session_id}')
def session_detail(session_id:uuid.UUID,user_id:uuid.UUID):
    session=owned(session_id,user_id)
    messages=db.all_rows('SELECT * FROM messages WHERE session_id=%s ORDER BY created_at,id',(session_id,))
    for m in messages: m['html']=markdown_html(m['content'])
    return {'session':session,'messages':messages,'artifacts':db.all_rows('SELECT id,message_id,title,kind,word_count,created_at FROM artifacts WHERE session_id=%s ORDER BY created_at',(session_id,)),
            'last_job':db.one("SELECT id,status,phase,error_message FROM jobs WHERE session_id=%s ORDER BY created_at DESC LIMIT 1",(session_id,)),
            'active_job':db.one("SELECT id,status,phase FROM jobs WHERE session_id=%s AND status IN ('queued','running')",(session_id,))}

@app.patch('/api/sessions/{session_id}')
def rename(session_id:uuid.UUID,body:RenameRequest):
    owned(session_id,body.user_id)
    db.execute('UPDATE sessions SET title=%s,updated_at=now() WHERE id=%s',(body.title.strip(),session_id))
    return {'ok':True}

@app.delete('/api/sessions/{session_id}')
def delete_session(session_id:uuid.UUID,user_id:uuid.UUID):
    owned(session_id,user_id)
    db.execute('DELETE FROM sessions WHERE id=%s',(session_id,))
    return {'ok':True}

@app.get('/api/library')
def library(q:str='',limit:int=30):
    return {'episodes':db.all_rows('SELECT id,title,guest,source_url,video_url,published FROM episodes WHERE title ILIKE %s OR guest ILIKE %s ORDER BY guest LIMIT %s',('%'+q[:200]+'%','%'+q[:200]+'%',max(1,min(limit,100))))}

@app.get('/api/artifacts/{artifact_id}')
def artifact(artifact_id:uuid.UUID,user_id:uuid.UUID):
    row=db.one('SELECT a.* FROM artifacts a JOIN sessions s ON s.id=a.session_id WHERE a.id=%s AND s.user_id=%s',(artifact_id,user_id))
    if not row: raise HTTPException(404,'Artifact not found.')
    row['html']=markdown_html(row['content']) if row['kind']=='markdown' else None
    return row

@app.post('/api/artifacts/{artifact_id}/html',status_code=201)
def convert_artifact_html(artifact_id:uuid.UUID,user_id:uuid.UUID):
    row=artifact(artifact_id,user_id)
    if row['kind'] != 'markdown': raise HTTPException(422,'Select a Markdown document to convert.')
    title=row['title'][:100]
    style='<style>body{background:#f8f5ed;color:#28352d;font:17px/1.7 system-ui,sans-serif;margin:0;padding:36px}main{max-width:800px;margin:auto}h1{font-size:2.2em;line-height:1.15}h2{margin-top:2em}li{margin-bottom:.7em}blockquote{border-left:3px solid #d47745;padding-left:18px}code{background:#ece9df;padding:3px}</style>'
    content=sanitize_html(style+'<main>'+markdown_html(row['content'])+'</main>')
    aid=uuid.uuid4()
    db.execute('INSERT INTO artifacts(id,session_id,message_id,title,kind,content,word_count) VALUES(%s,%s,%s,%s,%s,%s,%s)',(aid,row['session_id'],row['message_id'],title+' · HTML','html',content,row['word_count']))
    return {'id':aid,'session_id':row['session_id'],'kind':'html','conversion':'Markdown rendered as HTML; no new model claims'}

@app.get('/api/artifacts/{artifact_id}/preview')
def artifact_preview(artifact_id:uuid.UUID,user_id:uuid.UUID):
    row=artifact(artifact_id,user_id)
    return HTMLResponse(row['content'] if row['kind']=='html' else row['html'],headers={'Content-Security-Policy':CSP+"; sandbox; frame-ancestors 'self'"})

@app.post('/api/sessions/{session_id}/messages',status_code=202)
def send_message(session_id:uuid.UUID,body:ChatRequest):
    session=owned(session_id,body.user_id)
    if not body.message.strip(): raise HTTPException(422,'Please enter a message.')
    queue=db.one("SELECT count(*) AS n FROM jobs WHERE status IN ('queued','running')")['n']
    if queue>=8: raise HTTPException(429,{'code':'QUEUE_FULL','message':'The local model is busy. Please try again shortly.'})
    jid=uuid.uuid4(); mid=uuid.uuid4()
    try:
        with db.connection() as conn:
            conn.execute('INSERT INTO jobs(id,session_id,request) VALUES(%s,%s,%s)',(jid,session_id,Jsonb(body.model_dump(mode='json'))))
            conn.execute('INSERT INTO messages(id,session_id,role,content) VALUES(%s,%s,%s,%s)',(mid,session_id,'user',body.message.strip()))
            title=body.message.strip()[:65] if session['title']=='New conversation' else session['title']
            conn.execute('UPDATE sessions SET title=%s,updated_at=now() WHERE id=%s',(title,session_id))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409,{'code':'SESSION_BUSY','message':'This conversation already has a response in progress.'})
    executor.submit(process_job,jid,session_id,body.model_dump(mode='json'),mid)
    return {'job_id':jid,'status':'queued','user_message_id':mid}

def process_job(jid,sid,body,user_message_id):
    start=time.monotonic()
    def progress(phase):
        row = db.one("SELECT status FROM jobs WHERE id=%s",(jid,))
        current = row['status'] if row else 'cancelled'
        if current == 'cancelled': raise GenerationError('CANCELLED','The response was cancelled.')
        db.execute("UPDATE jobs SET status='running',phase=%s,updated_at=now() WHERE id=%s AND status IN ('queued','running')",(phase,jid))
    try:
        progress('Finding relevant transcript passages')
        history=db.all_rows('SELECT role,content FROM (SELECT role,content,created_at FROM messages WHERE session_id=%s AND id<>%s ORDER BY created_at DESC LIMIT 8) h ORDER BY created_at',(sid,user_message_id))
        prev=' '.join(m['content'] for m in history if m['role']=='user')[-2500:]
        sources=retrieve(body['message'],prev)
        mode=route(body['message'],body['mode'])
        log.info('retrieval_complete',extra={'event_data':{'job_id':str(jid),'sources':len(sources),'route':mode}})
        task_question=body['message']+(('\nTarget audience: '+body.get('audience','Product and growth teams')) if mode=='essay' else '')
        answer,art,meta=run_task(task_question,history,sources,body['provider'],mode,progress)
        progress('Saving your response')
        meta['duration_seconds']=round(time.monotonic()-start,1)
        meta['provider']=body['provider']
        mid=uuid.uuid4()
        with db.connection() as conn:
            active=conn.execute("SELECT status FROM jobs WHERE id=%s FOR UPDATE",(jid,)).fetchone()
            if not active or active['status']=='cancelled': return
            conn.execute('INSERT INTO messages(id,session_id,role,content,sources,metadata) VALUES(%s,%s,%s,%s,%s,%s)',(mid,sid,'assistant',answer,Jsonb(sources),Jsonb(meta)))
            if art:
                conn.execute('INSERT INTO artifacts(id,session_id,message_id,title,kind,content,word_count) VALUES(%s,%s,%s,%s,%s,%s,%s)',(uuid.uuid4(),sid,mid,art['title'],art['kind'],art['content'],art['word_count']))
            conn.execute("UPDATE jobs SET status='done',phase='Complete',message_id=%s,updated_at=now() WHERE id=%s",(mid,jid))
            conn.execute('UPDATE sessions SET updated_at=now() WHERE id=%s',(sid,))
        log.info('job_complete',extra={'event_data':{'job_id':str(jid),'seconds':meta['duration_seconds']}})
    except Exception as exc:
        code=exc.code if isinstance(exc,GenerationError) else 'GENERATION_FAILED'
        if code == 'CANCELLED': return
        message=exc.message if isinstance(exc,GenerationError) else 'Could not finish the response. Check the services and try again.'
        log.error('job_failed',extra={'event_data':{'job_id':str(jid),'code':code,'type':type(exc).__name__}})
        try: db.execute("UPDATE jobs SET status='error',error_code=%s,error_message=%s,updated_at=now() WHERE id=%s AND status IN ('queued','running')",(code,message,jid))
        except Exception: log.error('job_failure_not_persisted')

@app.post('/api/jobs/{job_id}/cancel')
def cancel_job(job_id:uuid.UUID,user_id:uuid.UUID):
    row=db.one('SELECT j.id,j.session_id FROM jobs j JOIN sessions s ON s.id=j.session_id WHERE j.id=%s AND s.user_id=%s',(job_id,user_id))
    if not row: raise HTTPException(404,'Job not found.')
    db.execute("UPDATE jobs SET status='cancelled',updated_at=now() WHERE id=%s AND status IN ('queued','running')",(job_id,))
    return {'ok':True}

@app.get('/api/jobs/{job_id}')
def job(job_id:uuid.UUID,user_id:uuid.UUID):
    row=db.one('SELECT j.id,j.session_id,j.status,j.phase,j.message_id,j.error_code,j.error_message FROM jobs j JOIN sessions s ON s.id=j.session_id WHERE j.id=%s AND s.user_id=%s',(job_id,user_id))
    if not row: raise HTTPException(404,'Job not found.')
    return row


@app.get('/docs',response_class=HTMLResponse)
def api_documentation():
    paths=app.openapi()['paths']
    rows=''.join('<tr><td>'+html.escape(method.upper())+'</td><td><code>'+html.escape(path)+'</code></td><td>'+html.escape(spec.get('summary',''))+'</td></tr>' for path,methods in paths.items() for method,spec in methods.items())
    return '<!doctype html><html><head><title>API reference</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font:16px/1.6 system-ui;max-width:1000px;margin:40px auto;padding:20px}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}code{overflow-wrap:anywhere}</style></head><body><h1>Lenny API reference</h1><p>Local single-user API. Supply user_id for session and artifact ownership. POST requests use application/json.</p><p><a href="/openapi.json">Full OpenAPI request and response schemas</a> · <a href="/">Open app</a></p><table><tr><th>Method</th><th>Path</th><th>Purpose</th></tr>'+rows+'</table><h2>Errors</h2><p>Errors return {error: {code, message, request_id}}. Validation: 422; missing or foreign record: 404; active conversation: 409; unavailable service: 503.</p></body></html>'

@app.get('/api/artifacts/{artifact_id}/download')
def download_artifact(artifact_id:uuid.UUID,user_id:uuid.UUID):
    row=artifact(artifact_id,user_id)
    name=re.sub(r'[^a-zA-Z0-9_-]+','-',row['title'])[:60] or 'artifact'
    suffix='html' if row['kind']=='html' else 'md'
    return Response(row['content'],media_type='text/html' if suffix=='html' else 'text/markdown',headers={'Content-Disposition':f'attachment; filename="{name}.{suffix}"','Content-Security-Policy':CSP+'; sandbox'})

class SaveInsight(BaseModel):
    user_id:uuid.UUID
    saved:bool

@app.patch('/api/messages/{message_id}/saved')
def save_insight(message_id:uuid.UUID,body:SaveInsight):
    row=db.one("SELECT m.id FROM messages m JOIN sessions s ON s.id=m.session_id WHERE m.id=%s AND s.user_id=%s AND m.role='assistant'",(message_id,body.user_id))
    if not row:raise HTTPException(404,'Response not found.')
    db.execute('UPDATE messages SET saved=%s WHERE id=%s',(body.saved,message_id))
    return {'saved':body.saved}

@app.get('/api/messages/{message_id}/saved')
def get_saved_insight(message_id:uuid.UUID,user_id:uuid.UUID):
    row=db.one("SELECT m.id,m.session_id,m.saved FROM messages m JOIN sessions s ON s.id=m.session_id WHERE m.id=%s AND s.user_id=%s AND m.role='assistant'",(message_id,user_id))
    if not row:raise HTTPException(404,'Response not found.')
    return row

@app.get('/api/insights')
def saved_insights(user_id:uuid.UUID):
    return {'insights':db.all_rows("SELECT m.id,m.session_id,m.content,m.created_at,s.title FROM messages m JOIN sessions s ON s.id=m.session_id WHERE s.user_id=%s AND m.saved=true ORDER BY m.created_at DESC LIMIT 100",(user_id,))}
