import http from 'node:http';
import { nativeStream } from './native-transport.mjs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdirSync } from 'node:fs';
import { createAgentSession, createExtensionRuntime, ModelRuntime, SessionManager, SettingsManager } from '@earendil-works/pi-coding-agent';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
try { process.loadEnvFile(path.join(root,'.env')); } catch {}
const agentDir=path.join(root,'data','pi-runtime');mkdirSync(agentDir,{recursive:true});
const runtime=await ModelRuntime.create({authPath:path.join(agentDir,'auth.json'),modelsPath:null,allowModelNetwork:false,refreshOnCreate:false});
const ollamaURL=(process.env.OLLAMA_BASE_URL||'http://127.0.0.1:11434').replace(/\/$/,'');
const localModel=process.env.OLLAMA_MODEL||'qwen3:4b-instruct-2507-q4_K_M';
runtime.registerProvider('lenny-local',{
  baseUrl:ollamaURL+'/v1',api:'openai-completions',apiKey:'ollama',
  models:[{id:localModel,name:'Local Qwen3',reasoning:false,input:['text'],
    contextWindow:8192,maxTokens:2048,cost:{input:0,output:0,cacheRead:0,cacheWrite:0},
    compat:{supportsStore:false,supportsDeveloperRole:false,supportsReasoningEffort:false,maxTokensField:'max_tokens'}}]
});
if(process.env.GEMINI_API_KEY) await runtime.setRuntimeApiKey('google',process.env.GEMINI_API_KEY);

const log=(event,data={})=>console.log(JSON.stringify({time:new Date().toISOString(),event,...data}));
const respond=(res,code,body)=>{res.writeHead(code,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(body));};
let active=false;
let geminiState="unverified";
http.createServer(async(req,res)=>{
  if(req.url==='/health'&&req.method==='GET') return respond(res,200,{status:'ok',agent:'Pi Coding Agent SDK',version:'1.1.0',geminiConfigured:!!process.env.GEMINI_API_KEY,geminiState});
  if(req.url!=='/generate'||req.method!=='POST')return respond(res,404,{error:{code:'NOT_FOUND'}});
  if(active)return respond(res,429,{error:{code:'AGENT_BUSY'}});
  let session,timer,timedOut=false,acquired=false;
  try{
    let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>180000)throw new Error('REQUEST_TOO_LARGE');}
    const body=JSON.parse(raw);
    if(!['ollama','gemini'].includes(body.provider)||typeof body.system!=='string'||typeof body.prompt!=='string')return respond(res,400,{error:{code:'INVALID_REQUEST'}});
    if(body.provider==='gemini'&&!process.env.GEMINI_API_KEY)return respond(res,503,{error:{code:'MISSING_KEY'}});
    const model=runtime.getModel(body.provider==='ollama'?'lenny-local':'google',body.provider==='ollama'?localModel:(process.env.GEMINI_MODEL||'gemini-3.8-flash'));
    if(!model)return respond(res,503,{error:{code:'MODEL_UNAVAILABLE'}});
    if(active)return respond(res,429,{error:{code:'AGENT_BUSY'}});
    active=true;acquired=true;
    const resourceLoader={
      getExtensions:()=>({extensions:[],errors:[],runtime:createExtensionRuntime()}),
      getSkills:()=>({skills:[],diagnostics:[]}),getPrompts:()=>({prompts:[],diagnostics:[]}),getThemes:()=>({themes:[],diagnostics:[]}),
      getAgentsFiles:()=>({agentsFiles:[]}),getSystemPrompt:()=>body.system,
      getSystemPromptSource:()=>undefined,getAppendSystemPrompt:()=>[],getAppendSystemPromptSources:()=>[],extendResources:()=>{},reload:async()=>{}
    };
    ({session}=await createAgentSession({cwd:root,agentDir,model,modelRuntime:runtime,thinkingLevel:'off',
      resourceLoader,noTools:true,tools:[],customTools:[],sessionManager:SessionManager.inMemory(root),
      settingsManager:SettingsManager.inMemory({compaction:{enabled:false},retry:{enabled:false},defaultTools:[],enableSkillCommands:false})}));
    session.agent.streamFunction=(m,context,options)=>nativeStream(m,context,options,{
      provider:body.provider,ollamaURL,key:process.env.GEMINI_API_KEY,
      maxTokens:Math.min(Math.max(body.maxTokens||1000,64),4096)
    });
    timer=setTimeout(()=>{timedOut=true;session.abort().catch(()=>{});},Math.min(body.timeoutSeconds||300,1200)*1000);
    const started=Date.now();
    await session.prompt(body.prompt,{expandPromptTemplates:false});
    const last=session.messages.filter(m=>m.role==='assistant').at(-1);
    if(timedOut)throw new Error('MODEL_TIMEOUT');
    if(last?.stopReason==='error'||last?.stopReason==='aborted'){
      const detail=String(last.errorMessage||'');
      
      const code=['PROVIDER_AUTH','PROVIDER_QUOTA','MODEL_UNAVAILABLE','NETWORK_ERROR','OUTPUT_TRUNCATED','EMPTY_RESPONSE'].includes(detail)?detail:/fetch failed|ECONNRESET|ETIMEDOUT|network|socket|Incomplete JSON segment/i.test(detail)?'NETWORK_ERROR':/401|403|UNAUTHENTICATED|API_KEY|authentication/i.test(detail)?'PROVIDER_AUTH':/429|RESOURCE_EXHAUSTED|quota/i.test(detail)?'PROVIDER_QUOTA':'MODEL_ERROR';
      if(body.provider==='gemini')geminiState=code==='PROVIDER_AUTH'?'authentication_failed':code==='PROVIDER_QUOTA'?'quota_exceeded':'error';
      log('provider_error',{provider:body.provider,stopReason:last.stopReason,code});
      throw new Error(code);
    }
    const text=session.getLastAssistantText()||'';
    if(body.provider==='gemini')geminiState='verified';
    log('generation_complete',{provider:body.provider,model:model.id,ms:Date.now()-started,characters:text.length});
    respond(res,200,{text,model:model.id,provider:body.provider});
  }catch(e){
    const code=timedOut?'MODEL_TIMEOUT':['REQUEST_TOO_LARGE','MODEL_ERROR','MODEL_UNAVAILABLE','PROVIDER_AUTH','PROVIDER_QUOTA','NETWORK_ERROR','OUTPUT_TRUNCATED','EMPTY_RESPONSE'].includes(e.message)?e.message:'MODEL_ERROR';
    // Do not log provider error bodies: they may include credentials or prompts.
    log('generation_error',{code,type:e.constructor.name});respond(res,502,{error:{code}});
  }finally{clearTimeout(timer);session?.dispose();if(acquired)active=false;}
}).listen(Number(process.env.AGENT_PORT||8787),process.env.AGENT_HOST||'127.0.0.1',()=>log('agent_ready',{port:Number(process.env.AGENT_PORT||8787)}));
