'use strict';
const $ = id => document.getElementById(id);
const state = { user: localStorage.getItem('lenny-user') || crypto.randomUUID(), session: null, sessions: [], artifacts: [], artifact: null, sources: [], status: null, busy: false, poll: null, preview: true, active_job_id: null };
localStorage.setItem('lenny-user', state.user);
let navigationVersion=0, artifactVersion=0, sessionsVersion=0;
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = value => { try { const u=new URL(value); return u.protocol==='https:' ? u.href : '#'; } catch { return '#'; } };
function timestampSeconds(value) {
  const match=String(value??'').trim().match(/^(\d+):([0-5]\d)(?::([0-5]\d))?$/);
  if(!match)return null;
  const first=Number(match[1]),second=Number(match[2]);
  return match[3]===undefined ? first*60+second : first*3600+second*60+Number(match[3]);
}
function videoReference(s) {
  if(!s.video_url)return '';
  let href=safeUrl(s.video_url),label='Watch episode';
  const seconds=timestampSeconds(s.timestamp);
  if(href!=='#'&&seconds!==null) {
    try {
      const url=new URL(href),host=url.hostname.toLowerCase().replace(/^www\./,'');
      if(host==='youtube.com'||host==='youtu.be') {
        url.searchParams.set('t',`${seconds}s`);
        href=url.href;label=`Watch at ${s.timestamp}`;
      }
    } catch {}
  }
  return ` &nbsp; <a href="${escape(href)}" target="_blank" rel="noopener noreferrer">${escape(label)} ↗</a>`;
}
async function api(path, options={}) {
  const response=await fetch(path,{headers:{'Content-Type':'application/json'},...options});
  const data=await response.json();
  if(!response.ok) throw new Error(data.error?.message || 'The request could not be completed.');
  return data;
}
function notify(text) { $('toast').textContent=text;$('toast').classList.remove('hidden');setTimeout(()=>$('toast').classList.add('hidden'),2800); }
function notice(text) { $('notice').textContent=text;$('notice').classList.toggle('hidden',!text); }
function setBusy(value,phase='Finding the right ideas…') { state.busy=value;$('send').disabled=value;$('working').classList.toggle('hidden',!value);$('working-label').textContent=phase; }
function scrollBottom() { $('messages-scroll').scrollTop=$('messages-scroll').scrollHeight; }
function modal(title,content) { $('sidebar').classList.remove('open');$('modal-title').textContent=title;$('modal-content').innerHTML=content;$('modal').showModal(); }

async function refreshStatus() {
  try {
    state.status=await api('/api/status');
    const s=state.status;
    if(!localStorage.getItem('lenny-provider')) $('provider').value=s.default_provider||'ollama';
    $('library-count').textContent=s.episodes;
    $('episode-count').textContent=`${s.episodes} podcast conversations`;
    $('index-status').textContent=s.episodes ? `${Number(s.chunks).toLocaleString()} searchable passages` : 'Your library is getting ready';
    const selected=s.providers.find(p=>p.id===$('provider').value);
    const ready=s.database && selected?.ready && s.episodes>0;
    $('connection-dot').classList.toggle('warn',!ready);
    $('connection-label').textContent=ready ? ($('provider').value==='ollama'?'Running locally':(s.gemini_state==='verified'?'Gemini connected':'Gemini key configured')) : (s.gemini_state==='quota_exceeded'&&$('provider').value==='gemini'?'Gemini quota reached':'Setup needed');
    if(!s.database) notice('The database is unavailable. Open Settings for setup details.');
    else if(!s.episodes) notice('No transcripts are indexed yet. Run the transcript import step in the README.');
    else if(!s.agent) notice('The Pi agent service is not running yet. Start it using the setup instructions.');
    else if(!selected?.ready) notice($('provider').value==='gemini'?(s.gemini_state==='authentication_failed'?'Google rejected the Gemini key. Update your private configuration and restart the agent, or use Local Ollama.':s.gemini_state==='quota_exceeded'?'Gemini quota is exhausted. Wait or choose Local Ollama.':'Gemini needs an API key. Open Settings for setup instructions, or use Local Ollama.'):'The local model is not ready yet. Its download may still be in progress.');
    else if(!state.busy) notice('');
  } catch { $('connection-label').textContent='Disconnected';$('connection-dot').classList.add('warn'); }
}
async function loadSessions() {
  const version=++sessionsVersion;
  const data=await api(`/api/sessions?user_id=${state.user}`);if(version!==sessionsVersion)return;state.sessions=data.sessions;
  $('sessions').innerHTML=data.sessions.length?data.sessions.map(s=>`<button class="session-button ${s.id===state.session?'active':''}" data-session="${s.id}" title="${escape(s.title)}"><span>◷</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left;">${escape(s.title)}</span><i data-delete="${s.id}" title="Delete chat" style="font-style:normal;opacity:0.5;margin-left:8px;">×</i></button>`).join(''):'<p class="quiet">Your research starts here.</p>';
}
function newChat() {
  navigationVersion++;state.active_job_id=null;state.sources=[];
  clearTimeout(state.poll);state.session=null;state.artifacts=[];state.artifact=null;
  $('messages').innerHTML='';$('welcome').classList.remove('hidden');$('chat-title').textContent='New conversation';
  closeArtifact();setBusy(false);notice('');$('prompt').value='';$('sidebar').classList.remove('open');
  $('messages-scroll').scrollTop=0;
  localStorage.removeItem('lenny-session');loadSessions().catch(e=>notice(e.message));$('prompt').focus();
}
async function openSession(id,{keepArtifact=false}={}) {
  const version=++navigationVersion;
  clearTimeout(state.poll);notice('');
  state.session=id;state.active_job_id=null;setBusy(true,'Loading conversation…');
  const data=await api(`/api/sessions/${id}?user_id=${state.user}`);
  if(version!==navigationVersion)return false;
  state.session=id;state.artifacts=data.artifacts;
  localStorage.setItem('lenny-session',id);
  $('chat-title').textContent=data.session.title;
  $('welcome').classList.toggle('hidden',data.messages.length>0);
  renderMessages(data.messages);
  $('sidebar').classList.remove('open');
  if(!keepArtifact) closeArtifact();
  if(data.active_job) {state.active_job_id=data.active_job.id; setBusy(true,data.active_job.phase);pollJob(data.active_job.id,id);} else {state.active_job_id=null; setBusy(false);if(data.last_job?.status==='error')notice(data.last_job.error_message);else if(data.last_job?.status==='cancelled')notice('Response cancelled.');}
  await loadSessions();if(version!==navigationVersion)return false;scrollBottom();return true;
}
function renderMessages(messages) {
  state.sources=[];
  $('messages').innerHTML=messages.map(m=>{
    const artifacts=state.artifacts.filter(a=>a.message_id===m.id);
    const sources=m.sources||[];
    const sourceHTML=sources.map(s=>{const i=state.sources.push(s)-1;return `<button class="source-chip" data-source="${i}" title="Read source: ${escape(s.title)}"><b>${escape(s.id)}</b>${escape(s.guest)}</button>`;}).join('');
    const meta=m.metadata||{};
    return `<article class="message ${m.role}"><div class="message-header"><span class="msg-avatar">${m.role==='user'?'Y':'✳'}</span><strong>${m.role==='user'?'You':'Lenny'}</strong><small>${m.role==='assistant'?escape((meta.provider==='gemini'?'Gemini':'Local Ollama')+(meta.duration_seconds?` · ${meta.duration_seconds}s`:'')):''}</small></div><div class="message-body prose">${m.html}</div>${sourceHTML?`<div class="source-list">${sourceHTML}</div>`:''}${artifacts.map(a=>`<button class="artifact-card" data-artifact="${a.id}"><span>▧</span><div><strong>${escape(a.title)}</strong><small>${a.kind==='html'?'HTML preview':'Markdown document'} · ${a.word_count.toLocaleString()} words</small></div><b>↗</b></button>`).join('')}${m.role==='assistant'?`<button class="text-button" data-save="${m.id}" data-saved="${!!m.saved}">${m.saved?'★ Saved insight':'☆ Save insight'}</button>`:''}${(meta.warnings||[]).map(w=>`<div class="warning">${escape(w)}</div>`).join('')}</article>`;
  }).join('');
}
async function submit(event) {
  event?.preventDefault();
  const message=$('prompt').value.trim();if(!message || state.busy)return;
  notice('');setBusy(true,'Starting your research…');
  const mode=$('mode').value,provider=$('provider').value;
  const version=navigationVersion;
  try {
    let sid=state.session;
    if(!sid){const s=await api('/api/sessions',{method:'POST',body:JSON.stringify({user_id:state.user})});sid=s.id;if(version===navigationVersion)state.session=sid;}
    const job=await api(`/api/sessions/${sid}/messages`,{method:'POST',body:JSON.stringify({user_id:state.user,message,mode,provider,audience:$('audience').value.trim()||'Product and growth teams'})});
    if(version!==navigationVersion){await loadSessions();return;}
    $('prompt').value='';$('prompt').style.height='';
    if(!await openSession(sid,{keepArtifact:true}))return;
    // openSession resumes the authoritative active job, including after refresh.
    if(!state.busy) { state.active_job_id=job.job_id; pollJob(job.job_id,sid); }
  } catch(e) {if(version===navigationVersion){setBusy(false);notice(e.message);}}
}
async function pollJob(id,sid) {
  if(state.session!==sid)return;
  try {
    const job=await api(`/api/jobs/${id}?user_id=${state.user}`);
    if(state.session!==sid)return;
    if(job.status==='done') {
      if(!await openSession(sid,{keepArtifact:true})||state.session!==sid)return;
      const artifact=state.artifacts.find(a=>a.message_id===job.message_id);
      if(artifact) await openArtifact(artifact.id);
      if(state.session===sid)setBusy(false);return;
    }
    if(job.status==='cancelled') {setBusy(false);state.active_job_id=null;notice('Response cancelled.');return;}
    if(job.status==='error') {setBusy(false);notice(job.error_message);return;}
    setBusy(true,job.phase);state.poll=setTimeout(()=>pollJob(id,sid),1600);
  } catch(e) {if(state.session===sid){setBusy(false);notice(e.message+' Refresh the conversation to resume tracking.');}}
}
async function openArtifact(id) {
  $('sidebar').classList.remove('open');
  const version=++artifactVersion,sid=state.session;
  const artifact=await api(`/api/artifacts/${id}?user_id=${state.user}`);
  if(version!==artifactVersion||sid!==state.session)return;
  state.artifact=artifact;state.preview=true;
  $('artifact-panel').classList.remove('hidden');$('workspace').classList.add('has-artifact');
  $('artifact-title').textContent=state.artifact.title;
  $('artifact-meta').textContent=`${state.artifact.kind.toUpperCase()} · ${state.artifact.word_count.toLocaleString()} words`;
  renderArtifact();
}
function closeArtifact() { artifactVersion++;$('artifact-panel').classList.add('hidden');$('workspace').classList.remove('has-artifact');state.artifact=null; }
async function convertToHTML() {
  if(!state.artifact||state.artifact.kind!=='markdown')return;
  try {const result=await api(`/api/artifacts/${state.artifact.id}/html?user_id=${state.user}`,{method:'POST'});await openSession(state.session,{keepArtifact:true});await openArtifact(result.id);notify('HTML version created');}catch(e){notice(e.message);}
}
function renderArtifact() {
  const a=state.artifact;if(!a)return;
  let convert=$('convert-html');if(!convert){convert=document.createElement('button');convert.id='convert-html';convert.textContent='Create HTML';convert.addEventListener('click',convertToHTML);$('copy-artifact').parentElement.append(convert);}convert.hidden=a.kind!=='markdown';
  $('preview-tab').classList.toggle('selected',state.preview);$('source-tab').classList.toggle('selected',!state.preview);
  $('artifact-body').replaceChildren();
  if(!state.preview){const pre=document.createElement('pre');pre.textContent=a.content;$('artifact-body').append(pre);return;}
  if(a.kind==='markdown'){const div=document.createElement('div');div.className='prose';div.innerHTML=a.html;$('artifact-body').append(div);}
  else {const iframe=document.createElement('iframe');iframe.setAttribute('sandbox','');iframe.setAttribute('referrerpolicy','no-referrer');iframe.title=a.title;iframe.src=`/api/artifacts/${a.id}/preview?user_id=${state.user}`;iframe.addEventListener('error',()=>notice('The artifact preview could not load. Try Source view.'));$('artifact-body').append(iframe);}
}
function showSource(i) {
  const s=state.sources[i];
  modal(s.guest,`<div class="modal-prose"><p>${escape(s.title)}</p><div class="source-label">${escape(s.id)} · Original transcript excerpt${s.timestamp?' · '+escape(s.timestamp):''}</div><div class="source-excerpt">${escape(s.text)}</div><p><a href="${escape(safeUrl(s.source_url))}" target="_blank" rel="noopener noreferrer">Open original transcript ↗</a>${videoReference(s)}</p><small>Source ID: ${escape(s.chunk_id)}. Citations identify retrieved evidence; review the excerpt before reusing a claim.</small></div>`);
}
async function showLibrary() {
  modal('The transcript library','<input class="search-input" id="library-search" placeholder="Find a guest or episode…" aria-label="Search transcript library"><div id="library-results" class="library-list">Loading episodes…</div>');
  let timer;
  const search=async()=>{try{const data=await api('/api/library?q='+encodeURIComponent($('library-search').value));if(!$('library-results'))return;$('library-results').innerHTML=data.episodes.length?data.episodes.map(e=>`<a class="library-item" href="${safeUrl(e.source_url)}" target="_blank" rel="noopener noreferrer"><strong>${escape(e.title)} ↗</strong><small>${escape(e.guest)}${e.published?' · '+escape(e.published):''}</small></a>`).join(''):'<p class="quiet">No episodes found.</p>';}catch(e){if($('library-results'))$('library-results').textContent=e.message;}};
  $('library-search').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(search,250);});await search();
}
async function showSettings() {
  await refreshStatus();const s=state.status||{};
  modal('Your workspace',`<div class="modal-prose"><p>A local research workspace. Your selected provider is always visible beside the message box.</p>${[['PostgreSQL',s.database],['Pi agent',s.agent],['Local Ollama',s.ollama],['Gemini key',s.gemini]].map(([name,ok])=>`<div class="status-row"><span>${name}</span><b>${ok?(name==='Gemini key'?'Configured · '+escape(s.gemini_state):'Connected'):'Needs setup'}</b></div>`).join('')}<p><strong>Local model:</strong> ${escape(s.providers?.[0]?.model||'qwen3:4b-instruct-2507-q4_K_M')}<br><strong>Cloud model:</strong> ${escape(s.providers?.[1]?.model||'gemini-3.8-flash')}</p><p>Local Ollama keeps generation on this computer. Gemini sends your request, recent conversation, and retrieved excerpts to Google. There is no automatic cloud fallback.</p><p>Configure your Gemini key in the project’s private <code>.env</code> file, then restart the agent service. Never put the key in a chat.</p><p><strong>Preview safety:</strong> HTML is sanitized and rendered in an iframe with no sandbox permissions. Scripts, forms, external resources, and parent-page access are blocked.</p><small>This is a single-user local demo, not a public multi-user service.</small></div>`);
}
$('chat-form').addEventListener('submit',submit);
$('prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();submit();}});
$('prompt').addEventListener('input',()=>{$('prompt').style.height='auto';$('prompt').style.height=Math.min($('prompt').scrollHeight,130)+'px';});
$('new-chat').addEventListener('click',newChat);
$('sessions').addEventListener('click',async e=>{
  const del=e.target.closest('[data-delete]');
  if(del) {
    e.stopPropagation();
    if(confirm('Delete this conversation?')){
      try{ await api(`/api/sessions/${del.dataset.delete}?user_id=${state.user}`,{method:'DELETE'});
      if(state.session===del.dataset.delete) newChat(); else await loadSessions();
      } catch(err){notice(err.message);}
    }
    return;
  }
  const b=e.target.closest('[data-session]');
  if(b)openSession(b.dataset.session).catch(err=>notice(err.message));
});
document.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',()=>{$('prompt').value=b.dataset.prompt;$('mode').value=b.dataset.mode;$('prompt').focus();}));
$('messages').addEventListener('click',e=>{const source=e.target.closest('[data-source]'),art=e.target.closest('[data-artifact]');if(source)showSource(Number(source.dataset.source));if(art)openArtifact(art.dataset.artifact).catch(err=>notice(err.message));});
$('close-artifact').addEventListener('click',closeArtifact);
$('cancel-button').addEventListener('click',async()=>{
  if(!state.active_job_id) return;
  try{
    await api(`/api/jobs/${state.active_job_id}/cancel?user_id=${state.user}`,{method:'POST'});
    setBusy(false); notice('Response cancelled. The current model request may take a moment to finish.'); clearTimeout(state.poll); state.active_job_id=null;
  } catch(e) { notice(e.message); }
});
$('preview-tab').addEventListener('click',()=>{state.preview=true;renderArtifact();});
$('source-tab').addEventListener('click',()=>{state.preview=false;renderArtifact();});
$('copy-artifact').addEventListener('click',async()=>{if(state.artifact){try{await navigator.clipboard.writeText(state.artifact.content);notify('Copied to clipboard');}catch{notify('Clipboard unavailable. Use Source view to copy.');}}});
$('download-artifact').addEventListener('click',()=>{if(state.artifact){const link=document.createElement('a');link.href=`/api/artifacts/${state.artifact.id}/download?user_id=${state.user}`;link.download='';document.body.append(link);link.click();link.remove();}});
$('library-button').addEventListener('click',showLibrary);
$('settings-button').addEventListener('click',showSettings);
$('about-button').addEventListener('click',()=>modal('A little wisdom, well sourced.','<div class="modal-prose"><p>The Lenny Growth Assistant helps you explore product and growth ideas from Lenny’s Podcast transcripts.</p><p>Ask a question, write an essay, or create a document. Open the source cards to check the original evidence behind each answer.</p><p>This is an independent candidate project, not an official Lenny product. Generated answers can make mistakes; verify the source before acting.</p></div>'));
$('close-modal').addEventListener('click',()=>$('modal').close());
$('modal').addEventListener('click',e=>{if(e.target===$('modal'))$('modal').close();});
$('menu-toggle').addEventListener('click',()=>$('sidebar').classList.toggle('open'));
$('provider').addEventListener('change',()=>{localStorage.setItem('lenny-provider',$('provider').value);notice('');refreshStatus();});
(async()=>{try{$('provider').value=localStorage.getItem('lenny-provider')||'ollama';await refreshStatus();await loadSessions();const previous=localStorage.getItem('lenny-session');if(previous&&state.sessions.some(s=>s.id===previous))await openSession(previous);}catch(e){notice(e.message);}})();

function setTheme(dark){document.documentElement.dataset.theme=dark?'dark':'light';localStorage.setItem('lenny-theme',dark?'dark':'light');$('theme-button').textContent=dark?'◐ Light mode':'◐ Dark mode';$('theme-button').setAttribute('aria-pressed',String(dark));}
setTheme(localStorage.getItem('lenny-theme')==='dark');
$('theme-button').addEventListener('click',()=>setTheme(document.documentElement.dataset.theme!=='dark'));
const updateAudience=()=>$('audience-wrap').classList.toggle('hidden',$('mode').value!=='essay');
$('mode').addEventListener('change',updateAudience);
document.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',updateAudience));
$('messages').addEventListener('click',async e=>{const b=e.target.closest('[data-save]');if(!b)return;try{const saved=b.dataset.saved!=='true';await api(`/api/messages/${b.dataset.save}/saved`,{method:'PATCH',body:JSON.stringify({user_id:state.user,saved})});b.dataset.saved=String(saved);b.textContent=saved?'★ Saved insight':'☆ Save insight';notify(saved?'Insight saved':'Insight removed');}catch(err){notice(err.message);}});
$('insights-button').addEventListener('click',async()=>{try{const data=await api(`/api/insights?user_id=${state.user}`);modal('Saved insights',data.insights.length?data.insights.map(i=>`<button class="library-item insight-link" data-open-session="${i.session_id}"><strong>${escape(i.title)}</strong><p>${escape(i.content.slice(0,220))}</p></button>`).join(''):'<p>Choose “Save insight” beneath an answer to keep it here.</p>');}catch(e){notice(e.message);}});
const topics=[['Product-market fit','How should a startup measure product-market fit?'],['Retention','What do guests recommend for improving user retention?'],['Product strategy','How should founders prioritize a product roadmap?'],['Growth experiments','How should teams choose and evaluate growth experiments?'],['Customer research','How can product teams learn from customer interviews?'],['Pricing','What advice do guests give about product pricing?']];
$('discover-button').addEventListener('click',()=>modal('Discover topics','<p>Choose a question to research in a new conversation. Sources appear after retrieval.</p>'+topics.map(([title,q],i)=>`<button class="library-item" data-discover="${i}"><strong>${escape(title)}</strong><p>${escape(q)}</p></button>`).join('')));
$('modal-content').addEventListener('click',e=>{const insight=e.target.closest('[data-open-session]'),topic=e.target.closest('[data-discover]');if(insight){$('modal').close();openSession(insight.dataset.openSession).catch(e=>notice(e.message));}if(topic){$('modal').close();newChat();$('prompt').value=topics[Number(topic.dataset.discover)][1];$('mode').value='answer';updateAudience();$('prompt').focus();}});
