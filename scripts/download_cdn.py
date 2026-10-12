"""Public jsDelivr mirror of the specified GitHub corpus; verify advertised hashes."""
import base64
import hashlib
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DEST=ROOT/'data'/'transcripts'
API='https://data.jsdelivr.com/v1/package/gh/ChatPRD/lennys-podcast-transcripts@main/flat'
CDN='https://cdn.jsdelivr.net/gh/ChatPRD/lennys-podcast-transcripts@main'

def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.parse.quote(url,safe=':/@'),timeout=60) as r:return r.read()
        except Exception:
            if attempt==2:raise
            time.sleep(1+attempt)

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    index=get(API)
    files=[f for f in json.loads(index)['files'] if f['name'].startswith('/episodes/') and f['name'].endswith('/transcript.md')]
    def download(f):
        parts=f['name'].strip('/').split('/')
        if len(parts)!=3 or parts[1] in ('.','..'):raise ValueError('Unexpected source path')
        path=(DEST/parts[1]/'transcript.md').resolve()
        if not path.is_relative_to(DEST.resolve()):raise ValueError('Unsafe path')
        content=path.read_bytes() if path.exists() else get(CDN+f['name'])
        digest=base64.b64encode(hashlib.sha256(content).digest()).decode()
        if f.get('hash') and digest!=f['hash']:
            content=get(CDN+f['name'])
            if base64.b64encode(hashlib.sha256(content).digest()).decode()!=f['hash']:raise ValueError('Source hash mismatch: '+parts[1])
        path.parent.mkdir(exist_ok=True);path.write_bytes(content)
        return parts[1]
    count=0;failed=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs={pool.submit(download,f):f for f in files}
        for job in as_completed(jobs):
            try:job.result();count+=1
            except Exception as e:failed.append({'path':jobs[job]['name'],'error':type(e).__name__})
            if (count+len(failed))%25==0:print(f'{count} episodes downloaded; {len(failed)} failed',flush=True)
    (DEST/'manifest.json').write_text(json.dumps({'url':CDN,'revision':'jsdelivr-index-sha256:'+hashlib.sha256(index).hexdigest(),'episodes':count,'expected':len(files),'failed':failed},indent=2))
    print(json.dumps({'downloaded':count,'expected':len(files),'failed':failed}),flush=True)
    if failed:raise SystemExit(1)

if __name__=='__main__':main()
