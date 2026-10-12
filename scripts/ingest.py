"""Idempotent, transactional ingestion. Run: python -m scripts.ingest"""
import hashlib
import json
import re
from pathlib import Path
import yaml
from backend import db
from backend.config import DATA_DIR

def parse_transcript(text):
    text=text.lstrip('\ufeff')
    meta={}
    if text.startswith('---'):
        pieces=text.split('---',2)
        if len(pieces)==3:
            meta=yaml.safe_load(pieces[1]) or {};text=pieces[2]
    return meta,text.strip()

def chunk_text(text,size=170,overlap=35):
    words=text.split()
    out=[]
    for start in range(0,len(words),size-overlap):
        chunk=' '.join(words[start:start+size])
        if len(chunk)<80: continue
        stamp=re.search(r'\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b',chunk)
        out.append((chunk,stamp.group(0) if stamp else None))
    return out

def source_metadata(meta,eid):
    title=str(meta.get('title',eid.replace('-',' ').title()))
    guest=str(meta.get('guest',eid.replace('-',' ').title()))
    video=str(meta.get('youtube_url',''))
    # This episode's upstream guest field misspells Alex Hardiman, even though
    # the title and transcript speaker line use the correct spelling.
    if eid=='alex-hardimen' and guest.strip().lower()=='alex hardimen':
        guest='Alex Hardiman'
    # Preserve downloaded source files, but do not publish a conflicting title or
    # an associated video link as verified episode identity.
    guest_terms=set(re.findall(r'[a-z]+',guest.lower()))-{'the','and'}
    title_terms=set(re.findall(r'[a-z]+',title.lower()))
    if '|' in title and guest_terms and not guest_terms.intersection(title_terms):
        return f'{guest} — transcript (upstream title mismatch)',guest,''
    return title,guest,video

def main():
    db.initialize()
    manifest=DATA_DIR/'manifest.json'
    revision=json.loads(manifest.read_text()).get('revision','manual-import') if manifest.exists() else 'manual-import'
    paths=sorted(DATA_DIR.glob('*/transcript.md'))
    if not paths: raise RuntimeError(f'No transcripts found in {DATA_DIR}. Run scripts/download_transcripts.py first.')
    changed=0
    for path in paths:
        raw=path.read_text(encoding='utf-8');digest=hashlib.sha256(('metadata-v3\n'+raw).encode()).hexdigest()
        eid=path.parent.name
        old=db.one('SELECT content_hash FROM episodes WHERE id=%s',(eid,))
        if old and old['content_hash']==digest: continue
        meta,body=parse_transcript(raw)
        title,guest,video=source_metadata(meta,eid)
        url=f'https://github.com/ChatPRD/lennys-podcast-transcripts/blob/main/episodes/{eid}/transcript.md'
        chunks=chunk_text(body)
        with db.connection() as conn:
            conn.execute('''INSERT INTO episodes(id,title,guest,source_url,video_url,published,content_hash,source_revision)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET title=excluded.title,
                guest=excluded.guest,source_url=excluded.source_url,video_url=excluded.video_url,
                published=excluded.published,content_hash=excluded.content_hash,source_revision=excluded.source_revision,indexed_at=now()''',
                (eid,title,guest,url,video,str(meta.get('publish_date','')),digest,revision))
            conn.execute('DELETE FROM chunks WHERE episode_id=%s',(eid,))
            with conn.cursor() as cur:
                cur.executemany('''INSERT INTO chunks(id,episode_id,ordinal,text,timestamp,search)
                    VALUES(%s,%s,%s,%s,%s,setweight(to_tsvector('english',%s),'A') || setweight(to_tsvector('english',%s),'B'))''',
                    [(f'{eid}:{i}',eid,i,text,stamp,title+' '+guest,text) for i,(text,stamp) in enumerate(chunks)])
        changed+=1
        if changed%25==0: print(f'Indexed {changed} episodes...',flush=True)
    print(json.dumps({'changed':changed,'discovered':len(paths),**db.one('SELECT (SELECT count(*) FROM episodes) AS episodes,(SELECT count(*) FROM chunks) AS chunks')}),flush=True)
    db.pool.close()

if __name__=='__main__':main()

