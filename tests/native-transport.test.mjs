import test from 'node:test';
import assert from 'node:assert/strict';
import {nativeStream} from '../agent/native-transport.mjs';

const model={id:'qwen3:4b-instruct-2507-q4_K_M',api:'openai-completions',provider:'lenny-local'};
const context={messages:[{role:'system',content:'Only cite supplied evidence.',sections:{rules:'Do not invent.'}},{role:'user',content:'Return a brief.'}]};
const config={provider:'ollama',ollamaURL:'http://localhost:11434',maxTokens:850};
const originalFetch=globalThis.fetch;
test.afterEach(()=>{globalThis.fetch=originalFetch;});

test('local transport carries instructions, output budget and nonthinking boundary',async()=>{
  globalThis.fetch=async(url,request)=>{
    const payload=JSON.parse(request.body);
    assert.ok(url.endsWith('/api/chat'));
    assert.match(payload.messages[0].content,/Only cite supplied evidence\./);
    assert.match(payload.messages[0].content,/Do not invent\./);
    assert.equal(payload.think,undefined);
    assert.equal(payload.options.num_predict,850);
    assert.equal(payload.stream,true);
    return Response.json({response:'<main>Brief [S1]</main>',done:true,done_reason:'stop'});
  };
  const result=await nativeStream(model,context,{},config).result();
  assert.equal(result.stopReason,'stop');assert.match(result.content[0].text,/<main>/);
});
for(const [name,response,code] of [
  ['truncation',()=>Response.json({response:'unfinished',done:true,done_reason:'length'}),'OUTPUT_TRUNCATED'],
  ['empty',()=>Response.json({response:'',done:true,done_reason:'stop'}),'EMPTY_RESPONSE'],
  ['quota',()=>new Response('secret context',{status:429}),'PROVIDER_QUOTA'],
  ['auth',()=>new Response('secret key',{status:401}),'PROVIDER_AUTH'],
  ['unavailable',()=>new Response('',{status:404}),'MODEL_UNAVAILABLE'],
  ['bad JSON',()=>new Response('{broken'),'NETWORK_ERROR']]){
  test(name+' becomes a safe typed error',async()=>{
    globalThis.fetch=async()=>response();
    const result=await nativeStream(model,context,{},config).result();
    assert.equal(result.errorMessage,code);assert.equal(result.stopReason,'error');assert.deepEqual(result.content,[]);
  });
}
test('Ollama NDJSON survives split UTF-8 and partial lines',async()=>{
  const bytes=new TextEncoder().encode(JSON.stringify({message:{content:'Café '}})+'\n'+JSON.stringify({message:{content:'[S1]'},done:true,done_reason:'stop'})+'\n');
  globalThis.fetch=async()=>new Response(new ReadableStream({start(controller){for(let i=0;i<bytes.length;i+=3)controller.enqueue(bytes.slice(i,i+3));controller.close();}}));
  const result=await nativeStream(model,context,{},config).result();
  assert.equal(result.content[0].text,'Café [S1]');
});
test('Ollama disconnected stream is not a completed answer',async()=>{
  globalThis.fetch=async()=>Response.json({message:{content:'unfinished'}});
  assert.equal((await nativeStream(model,context,{},config).result()).errorMessage,'NETWORK_ERROR');
});
test('Gemini preserves system instructions and excludes thought parts',async()=>{
  globalThis.fetch=async(url,request)=>{
    const body=JSON.parse(request.body);
    assert.match(body.systemInstruction.parts[0].text,/Do not invent/);
    assert.equal(request.headers['x-goog-api-key'],'fixture-only');
    return Response.json({candidates:[{finishReason:'STOP',content:{parts:[{thought:true,text:'private thought'},{text:'Supported [S1]'}]}}]});
  };
  const result=await nativeStream({...model,id:'gemini-3.8-flash'},context,{}, {...config,provider:'gemini',key:'fixture-only'}).result();
  assert.equal(result.content[0].text,'Supported [S1]');
});
