"""Download only transcript files from the public source archive. No Git CLI required."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
DEST=ROOT/'data'/'transcripts'
URL='https://codeload.github.com/ChatPRD/lennys-podcast-transcripts/tar.gz/refs/heads/main'

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(URL,headers={'User-Agent':'LennyGrowthAssistant/1.0'})
    print('Downloading public transcript archive...',flush=True)
    with urllib.request.urlopen(req,timeout=120) as response:
        payload=response.read(150_000_001)
    if len(payload)>150_000_000: raise ValueError('Archive exceeds 150 MB safety limit')
    revision='archive-sha256:'+hashlib.sha256(payload).hexdigest()
    count=0
    with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
        for member in archive:
            parts=PurePosixPath(member.name).parts
            if not member.isfile() or len(parts)!=4 or parts[1]!='episodes' or parts[3]!='transcript.md': continue
            if member.size>5_000_000 or parts[2] in ('.','..'): continue
            target=(DEST/parts[2]/'transcript.md').resolve()
            if not target.is_relative_to(DEST.resolve()): raise ValueError('Unsafe archive path')
            target.parent.mkdir(parents=True,exist_ok=True)
            stream=archive.extractfile(member)
            if stream: target.write_bytes(stream.read());count+=1
    if not count: raise RuntimeError('No transcript files were found; check source archive structure')
    (DEST/'manifest.json').write_text(json.dumps({'url':URL,'revision':revision,'episodes':count},indent=2))
    print(f'Downloaded {count} episodes. Source snapshot: {revision}',flush=True)

if __name__=='__main__':main()

