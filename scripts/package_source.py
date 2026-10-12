"""Create a source-only handoff archive; never recursively include private data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json

ROOT=Path(__file__).resolve().parents[1]
TOP=['README.md','SETUP.md','PRD.md','design.md','architecture.md','REQUIREMENTS.md',
     '.env.example','.gitignore','.dockerignore','start.ps1','stop.ps1',
     'bootstrap.ps1','bootstrap.sh','compose.yaml','compose.gpu.yaml','compose.ollama.yaml']
ALLOWED={'.py','.sql','.txt','.md','.js','.mjs','.html','.css','.svg'}
paths=[ROOT/name for name in TOP]
for directory in ['backend','frontend','scripts','skills','tests','docs']:
    for p in (ROOT/directory).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and (p.suffix in ALLOWED or p.name=='Dockerfile'):
            paths.append(p)
paths += [ROOT/'agent'/name for name in ['package.json','package-lock.json','server.mjs','native-transport.mjs','Dockerfile']]
out=ROOT/'deliverables'
out.mkdir(exist_ok=True)
archive=out/'lenny-growth-assistant-source.zip'
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for p in sorted(set(paths)):
        z.write(p,Path('lenny-growth-assistant')/p.relative_to(ROOT))
with ZipFile(archive) as z:
    names=z.namelist()
    forbidden=['/.env','/node_modules/','/data/','/logs/','/.venv/','test_auth.json']
    for name in names:
        if name.endswith('/.env.example'): continue
        if any(part in name for part in forbidden):
            raise RuntimeError('Unexpected private file in source archive')
(out/'manifest.json').write_text(json.dumps({'archive':archive.name,'files':names},indent=2))
print(f'Created {archive.name}: {len(names)} source files, {archive.stat().st_size:,} bytes. No private environment, corpus or runtime logs included.')
