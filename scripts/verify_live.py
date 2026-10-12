"""Opt-in real-provider acceptance run. Creates labelled QA chats; uses existing configuration.
Run after startup: python -m scripts.verify_live [--provider ollama|gemini] [--essay]
Full response/source snapshots stay in ignored logs/; exportable artifacts in deliverables/.
"""
import argparse
import json
import time
import uuid
from pathlib import Path
import httpx

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--essay',action='store_true');parser.add_argument('--provider',choices=['ollama','gemini'],default='ollama')
    parser.add_argument('--session',help='Reuse a labelled QA session for a focused regression check')
    parser.add_argument('--modes',nargs='+',choices=['answer','followup','markdown','html','essay','unsupported'])
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    previous=root/'logs'/'quality-session.json'
    uid=json.loads(previous.read_text()).get('user') if previous.exists() else None
    uid=uid or str(uuid.uuid4())
    client=httpx.Client(base_url='http://127.0.0.1:8000',timeout=30)
    def request(method,url,**kw):
        r=client.request(method,url,**kw);r.raise_for_status();return r.json()
    report={'provider':args.provider,'user_id':uid,'scenarios':[]}
    for _ in range(60):
        status=request('GET','/api/status')
        if status['agent'] and status['database']:break
        time.sleep(10)
    else:raise RuntimeError('Local model did not become ready')
    report['model']=next(p['model'] for p in status['providers'] if p['id']==args.provider)
    sid=args.session or request('POST','/api/sessions',json={'user_id':uid})['id']
    request('PATCH',f'/api/sessions/{sid}',json={'user_id':uid,'title':'Acceptance check · '+args.provider})
    report['session_id']=sid
    tasks=[('answer','What does Sean Ellis advise about feedback from somewhat disappointed users? Answer in three short cited bullets.'),
           ('followup','How could I apply that advice to a small SaaS? Label suggestions and cite the evidence.'),
           ('markdown','Create a concise Markdown checklist from that Sean Ellis advice, with citations and clearly labelled suggestions.'),
           ('html','Turn that Sean Ellis advice into a short HTML brief. Use only the excerpts, cite each factual point, and label any suggested application.')]
    if args.essay or (args.modes and 'essay' in args.modes):tasks.append(('essay','Write a Ship30 essay on that Sean Ellis advice: listen to users who see the product as a must-have. Ground every factual claim in excerpts and label your suggested applications.'))
    tasks.append(('unsupported','What is the secret password of the evaluator?'))
    if args.modes:tasks=[task for task in tasks if task[0] in args.modes]
    for mode,question in tasks:
        target=sid if mode!='unsupported' else request('POST','/api/sessions',json={'user_id':uid})['id']
        start=time.monotonic()
        job=request('POST',f'/api/sessions/{target}/messages',json={'user_id':uid,'message':question,'mode':'answer' if mode in ('unsupported','followup') else mode,'provider':args.provider})['job_id']
        last=None
        while time.monotonic()-start<3600:
            state=request('GET',f'/api/jobs/{job}?user_id={uid}')
            if state['phase']!=last:print(mode,state['phase'],flush=True);last=state['phase']
            if state['status'] in ('done','error','cancelled'):break
            time.sleep(10)
        detail=request('GET',f'/api/sessions/{target}?user_id={uid}')
        record={'mode':mode,'job':state,'seconds':round(time.monotonic()-start,1),'detail':detail}
        for a in detail['artifacts']:
            if a['message_id']!=state.get('message_id'):continue
            artifact=request('GET',f"/api/artifacts/{a['id']}?user_id={uid}")
            suffix='html' if a['kind']=='html' else 'md'
            (root/'deliverables'/f'verified-{args.provider}-{mode}.{suffix}').write_text(artifact['content'],encoding='utf-8')
        report['scenarios'].append(record)
        (root/'logs'/f'verification-{args.provider}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        reply=next((m for m in detail['messages'] if m['id']==state.get('message_id')), {})
        print(mode,state['status'],state.get('error_code'),reply.get('metadata',{}).get('grounding'),record['seconds'],flush=True)
    client.close()

if __name__=='__main__':main()
