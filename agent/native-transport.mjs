import { createAssistantMessageEventStream, getSystemMessageText } from '@earendil-works/pi-ai';

const textOf = value => typeof value === 'string' ? value : (value || []).filter(x => x.type === 'text').map(x => x.text).join('\n');

// Read Ollama NDJSON incrementally so long generations do not hit the HTTP client's
// response-header timeout. Buffer complete lines, never parse arbitrary byte chunks.
async function readOllama(response) {
  const reader=response.body.getReader(),decoder=new TextDecoder();
  let pending='',output='',last={},finished=false;
  const consume=line=>{
    if(!line.trim())return;
    const item=JSON.parse(line);
    if(item.error)throw new Error('MODEL_ERROR');
    output+=item.message?.content||item.response||'';
    last=item;if(item.done)finished=true;
  };
  try {
    while(true){
      const {value,done}=await reader.read();
      pending+=decoder.decode(value,{stream:!done});
      const lines=pending.split('\n');pending=lines.pop();
      for(const line of lines)consume(line);
      if(done)break;
    }
    consume(pending);
    if(!finished)throw new Error('NETWORK_ERROR');
    return {...last,message:{content:output}};
  } finally {reader.releaseLock();}
}

// Pi owns the agent lifecycle and receives only the finished, validated response.
export function nativeStream(model, context, options, config) {
  const stream = createAssistantMessageEventStream();
  const message = { role:'assistant', content:[], api:model.api, provider:model.provider,
    model:model.id, timestamp:Date.now(), stopReason:'stop',
    usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}} };
  (async () => {
    try {
      const messages = context.messages.map(m => ({role:m.role, content:m.role === 'system' ? getSystemMessageText(m) : textOf(m.content)}));
      let endpoint, headers={'Content-Type':'application/json'}, payload;
      if(config.provider === 'ollama') {
        endpoint=config.ollamaURL+'/api/chat';
        payload={model:model.id,messages,stream:true,...(/instruct/i.test(model.id)?{}:{think:false}),
          options:{temperature:0.2,num_predict:config.maxTokens,num_ctx:8192}};

      } else {
        endpoint='https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(model.id)+':generateContent';
        headers['x-goog-api-key']=config.key;
        payload={systemInstruction:{parts:[{text:messages.filter(m=>m.role==='system').map(m=>m.content).join('\n')}]},
          contents:messages.filter(m=>m.role!=='system').map(m=>({role:m.role==='assistant'?'model':'user',parts:[{text:m.content}]})),
          generationConfig:{temperature:0.2,maxOutputTokens:config.maxTokens,
            ...(/^gemini-3/.test(model.id)?{thinkingConfig:{thinkingLevel:'low'}}:{})}};
      }
      const response=await fetch(endpoint,{method:'POST',headers,body:JSON.stringify(payload),signal:AbortSignal.any([...(options.signal?[options.signal]:[]),AbortSignal.timeout(config.provider==='gemini'?120000:900000)])});
      if(!response.ok) {
        // Never retain a provider response body: it can contain sensitive context.
        await response.body?.cancel();
        throw new Error(response.status===429?'PROVIDER_QUOTA':[401,403].includes(response.status)?'PROVIDER_AUTH':response.status===404?'MODEL_UNAVAILABLE':response.status>=500?'NETWORK_ERROR':'MODEL_ERROR');
      }
      let data;
      try {data=config.provider==='ollama'?await readOllama(response):await response.json();} catch(error) {throw new Error(error.message==='MODEL_ERROR'?'MODEL_ERROR':'NETWORK_ERROR');}
      let output, reason;
      if(config.provider==='ollama') {
        output=data.message?.content||data.response||''; reason=data.done_reason;
        message.usage.input=data.prompt_eval_count||0;message.usage.output=data.eval_count||0;
      } else {
        const candidate=data.candidates?.[0];
        output=(candidate?.content?.parts||[]).filter(p=>!p.thought).map(p=>p.text||'').join('');reason=candidate?.finishReason;
        message.usage.input=data.usageMetadata?.promptTokenCount||0;message.usage.output=data.usageMetadata?.candidatesTokenCount||0;
      }
      message.usage.totalTokens=message.usage.input+message.usage.output;
      if(reason==='length'||reason==='MAX_TOKENS')throw new Error('OUTPUT_TRUNCATED');
      if(!output.trim())throw new Error('EMPTY_RESPONSE');
      stream.push({type:'start',partial:message});
      message.content.push({type:'text',text:''});stream.push({type:'text_start',contentIndex:0,partial:message});
      message.content[0].text=output;stream.push({type:'text_delta',contentIndex:0,delta:output,partial:message});
      stream.push({type:'text_end',contentIndex:0,content:output,partial:message});
      stream.push({type:'done',reason:'stop',message});
    } catch(error) {
      const known=['PROVIDER_QUOTA','PROVIDER_AUTH','MODEL_UNAVAILABLE','MODEL_ERROR','NETWORK_ERROR','OUTPUT_TRUNCATED','EMPTY_RESPONSE'];
      message.stopReason=options.signal?.aborted?'aborted':'error';
      message.errorMessage=known.includes(error.message)?error.message:'NETWORK_ERROR';
      stream.push({type:'error',reason:message.stopReason,error:message});
    }
  })();
  return stream;
}
