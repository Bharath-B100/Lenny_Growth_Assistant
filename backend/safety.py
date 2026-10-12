import re
import html
import bleach
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

MARKDOWN = MarkdownIt('commonmark', {'html': False, 'linkify': False}).enable('table')
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src 'none'; script-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
TAGS = ['html','head','body','title','meta','style','main','section','article','header','footer','nav','aside','div','span','p','h1','h2','h3','h4','h5','h6','strong','b','em','i','ul','ol','li','blockquote','pre','code','hr','br','table','thead','tbody','tr','th','td','caption','a','dl','dt','dd']

def sanitize_html(raw):
    raw = re.sub(r'^```(?:html)?\s*|\s*```$', '', raw.strip(), flags=re.I)
    soup = BeautifulSoup(raw,'html.parser')
    for tag in soup(['script','iframe','object','embed','form','input','button','link','base','meta','svg','math','video','audio','img']):
        tag.decompose()
    # Links are text-only in artifacts: no navigation away from the sandbox.
    for tag in soup.find_all(True):
        tag.attrs = {k:v for k,v in tag.attrs.items() if k in ('class','id','colspan','rowspan')}
    for wrapper in soup.find_all(['html','head','body']):
        wrapper.unwrap()
    clean = bleach.clean(str(soup), tags=TAGS, attributes={'*':['class','id'],'td':['colspan','rowspan'],'th':['colspan','rowspan']}, strip=True)
    # CSS may express url(); CSP blocks all network requests. Remove imports too.
    clean = re.sub(r'@import\s+[^;]+;', '', clean, flags=re.I)
    return '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+html.escape(CSP, quote=True)+'"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'+clean+'</body></html>'

def markdown_html(text):
    return bleach.clean(MARKDOWN.render(text), tags=[t for t in TAGS if t not in ('style','meta','html','body','head')], attributes={'a':['href','title'],'th':['align'],'td':['align']}, protocols=['https','http'], strip=True)

def citation_ids(text):
    return {identifier for group in re.findall(r'\[((?:S\d+)(?:\s*,\s*S\d+)*)\]', text) for identifier in re.findall(r'S\d+', group)}

def word_count(text):
    return len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", re.sub(r'\[S\d+(?:\s*,\s*S\d+)*\]','',text)))



ARTIFACT_STYLE = '<style>body{margin:0;background:#f8f5ed;color:#26392e;font:17px/1.65 system-ui,sans-serif;padding:clamp(18px,5vw,48px)}main{max-width:820px;margin:auto}h1{font-size:clamp(26px,4vw,40px);line-height:1.15}h2{margin-top:1.7em;font-size:23px}li{margin-bottom:12px}strong{color:#9b4927}blockquote{border-left:3px solid #c26b3b;padding-left:16px}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #ccc;text-align:left}pre{white-space:pre-wrap}</style>'

def render_ai_html(fragment):
    return sanitize_html(ARTIFACT_STYLE+fragment)
