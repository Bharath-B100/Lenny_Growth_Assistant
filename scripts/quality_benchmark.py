"""Run the PRD's 20 supported + 5 unsupported local answer checks.

Creates labelled disposable conversations under a separate local user identity.
Results and source excerpts are saved only in ignored logs/quality-benchmark-*.json.
The script records evidence for human claim scoring; it does not mark citations as
correct merely because IDs exist or the model reviewer approves a draft.
"""
import json
import time
import uuid
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
SUPPORTED=[
 ('pmf','Sean Ellis product market fit how would users feel without product','Sean Ellis','survey condition; dependence not current dissatisfaction'),
 ('discovery','Teresa Torres continuous discovery habits user interviews weekly','Teresa Torres','continuous discovery habits and customer interviews'),
 ('positioning','April Dunford product positioning competitive alternatives differentiated value','April Dunford','competitive alternatives and differentiated value'),
 ('dhm','Gibson Biddle DHM delight hard to copy margin product strategy','Gibson Biddle','delight customers, hard to copy, margin enhancing'),
 ('pmf-survey','Rahul Vohra Superhuman product market fit survey very disappointed','Rahul Vohra','survey and very disappointed segment'),
 ('retention','Elena Verna retention improve growth tactics retention levers','Elena Verna','retention or churn guidance'),
 ('growth-loops','Casey Winters growth loops kindle fire strategies acquisition channels','Casey Winters','early non-scalable kindle vs scalable fire strategies'),
 ('prioritization','Shreyas Doshi product prioritization strategy product work','Shreyas Doshi','prioritization pitfall or levels of product work'),
 ('pricing','Patrick Campbell SaaS pricing value customer willingness to pay','Patrick Campbell','pricing and customer-perceived value'),
 ('jtbd','Bob Moesta jobs to be done progress customer struggle interview','Bob Moesta','customer progress and jobs-to-be-done interviews'),
 ('scaling','Claire Hughes Johnson scaling people operating cadence company principles','Claire Hughes Johnson','operating cadence and operating principles'),
 ('growth-model','Brian Balfour growth model channels product market fit','Brian Balfour','growth model or channel-market fit'),
 ('brand','Arielle Jackson brand positioning company story customer','Arielle Jackson','brand positioning and customer problem'),
 ('growth-team','Adam Fishman high performing growth team onboarding metrics','Adam Fishman','onboarding reaches all users or growth team practices'),
 ('monetization','Madhavan Ramanujam monetizing innovation pricing customers willingness to pay','Madhavan Ramanujam','price before building or willingness to pay'),
 ('management','Julie Zhuo manager feedback one on ones team leadership','Julie Zhuo','manager feedback or one-on-one practice'),
 ('habits','Nir Eyal habit forming product trigger action reward investment','Nir Eyal','Hooked habit-forming model'),
 ('product-teams','Marty Cagan empowered product teams discovery outcomes','Marty Cagan','empowered teams and outcomes'),
 ('nytimes-product','Alex Hardiman New York Times product development audience engagement','Alex Hardiman','NYT product and audience/mission'),
 ('strategy-stack','Ravi Mehta product strategy mission roadmap goals strategy stack','Ravi Mehta','strategy connects company mission to roadmap and goals'),
]
UNSUPPORTED=[
 ('future-episode','What will the next Lenny podcast episode next week be about?'),
 ('private-metric','What is the exact number of active users in my private SaaS today?'),
 ('recording-detail','What exact brand of coffee did Sean Ellis drink during the recording?'),
 ('credential','What is the secret password of the evaluator?'),
 ('unavailable-forecast','What will tomorrow weather be on Mars at 9 AM?'),
]

def main():
    out=ROOT/'logs'/f'quality-benchmark-ollama-{time.strftime("%Y%m%d-%H%M%S")}.json'
    uid=str(uuid.uuid4());report={'provider':'ollama','model':None,'user_id':uid,'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'supported':[],'unsupported':[],'stopped_on_quota':False}
    out.parent.mkdir(exist_ok=True)
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as client:
        status=client.get('/api/status');status.raise_for_status();status=status.json()
        if not status['database'] or not status['agent'] or not status['ollama']:
            raise SystemExit('Local database, Pi agent and Ollama must be ready.')
        report['model']=next(p['model'] for p in status['providers'] if p['id']=='ollama')
        cases=[('supported',c[0],c[1],{'guest':c[2],'manual_check':c[3]}) for c in SUPPORTED]
        cases += [('unsupported',c[0],c[1],{}) for c in UNSUPPORTED]
        for group,key,question,criteria in cases:
            sid=client.post('/api/sessions',json={'user_id':uid});sid.raise_for_status();sid=sid.json()['id']
            client.patch(f'/api/sessions/{sid}',json={'user_id':uid,'title':f'Quality check · {key}'}).raise_for_status()
            start=time.monotonic()
            response=client.post(f'/api/sessions/{sid}/messages',json={'user_id':uid,'message':question,'mode':'answer','provider':'ollama'})
            response.raise_for_status();jid=response.json()['job_id']
            while True:
                r=client.get(f'/api/jobs/{jid}',params={'user_id':uid});r.raise_for_status();job=r.json()
                if job['status'] in ('done','error','cancelled'):break
                time.sleep(5)
            detail=client.get(f'/api/sessions/{sid}',params={'user_id':uid});detail.raise_for_status();detail=detail.json()
            answer=next((m for m in detail['messages'] if m['id']==job.get('message_id')),None)
            record={'case':key,'question':question,'criteria':criteria,'job':job,'seconds':round(time.monotonic()-start,1),
                    'answer':answer['content'] if answer else None,'metadata':answer['metadata'] if answer else {},
                    'sources':answer['sources'] if answer else [],'expected':'cited answer; human score required' if group=='supported' else 'insufficient-evidence abstention'}
            report[group].append(record)
            out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(group,key,job['status'],job.get('error_code'),record['metadata'].get('grounding'),record['seconds'],flush=True)
    report['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Results: {out.relative_to(ROOT)}')

if __name__=='__main__':main()
