// Model-free contracts against the actual component handlers and media client.
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const out = path.join(root, 'runtime/pre-freeze-productization'); fs.mkdirSync(out, {recursive:true});
function load(relative, mocks={}) {
  const filename=path.join(root,relative), m=new Module(filename,module); m.filename=filename; m.paths=module.paths;
  m.require=(name)=>name in mocks?mocks[name]:require(name);
  m._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,filename);
  return m.exports;
}
const checks=[]; const flush=async()=>{for(let i=0;i<8;i++) await new Promise(setImmediate);};
async function componentContracts() {
  let slots=[],cursor=0,trace=[],callbacks,starts=[],stops=0,slow=false,resolveAvatar,failSound=false,slowSound=false,resolveSound;
  const hooks={useRef(v){const i=cursor++;return slots[i]??=( {current:v} );},useState(v){const i=cursor++;if(!(i in slots))slots[i]=v;return [slots[i],x=>{slots[i]=typeof x==='function'?x(slots[i]):x;}];},useEffect(){}};
  const jsx=(type,props)=>({type,props});
  const avatar={disconnect(){trace.push('avatar-disconnect');},unlockSound(){trace.push('unlock');return failSound?Promise.reject(Error('sound denied')):slowSound?new Promise(r=>resolveSound=r):Promise.resolve();},async connect(){trace.push('avatar-connect');if(slow)await new Promise(r=>resolveAvatar=r);},binding(){return {control_id:'control',client_id:'client',sessionid:'rtc'};},readyForSpeech(){return true;}};
  class Socket {
    connect(c){trace.push('ws-connect');callbacks=c;c.onConnectionState('connected');queueMicrotask(()=>c.onEvent({type:'session_ready',session_id:'ws',turn_id:0,data:{}}));}
    disconnect(){} sendStart(o){trace.push('start');starts.push(o);} sendStop(){stops++;}
  }
  global.AudioContext=class {state='suspended';resume(){trace.push('resume');this.state='running';return Promise.resolve();}};
  const {VoiceConsole}=load('frontend/src/components/VoiceConsole.tsx',{
    react:hooks,'react/jsx-runtime':{jsx,jsxs:jsx},'@/components/AvatarVideo':{AvatarVideo:'AvatarVideo'},
    '@/lib/expression-controller':{expressionController:{reset(){}},EXPRESSION_NAMES:[]},'@/lib/mouth-controller':{mouthController:{stop(){},reset(){}}},'@/lib/websocket':{VoiceSocket:Socket},
  });
  function nodes(node){return node&&typeof node==='object'?[node,...Object.values(node.props??{}).flatMap(v=>Array.isArray(v)?v.flatMap(nodes):nodes(v))]:[];}
  function render(){cursor=0;const tree=VoiceConsole();nodes(tree).find(n=>n.type==='AvatarVideo').props.ref.current=avatar;return nodes(tree);}
  const button=(ns,cls)=>ns.find(n=>n.type==='button'&&n.props.className===cls);
  let ns=render();assert.equal(ns.find(n=>n.type==='details').props.open,undefined);
  assert.equal(ns.find(n=>n.type==='select').props.value,'avatar_webrtc');
  assert(!ns.some(n=>n.type==='button'&&['开启声音','开始对话','连接数字人'].includes(n.props.children)));
  button(ns,'primary').props.onClick();assert.deepEqual(trace.slice(-3),['resume','avatar-disconnect','unlock']);
  // A second click during pending preparation cannot launch a second session.
  button(ns,'primary').props.onClick();await flush();assert.equal(starts.length,1);
  assert.deepEqual(trace.filter(x=>['unlock','avatar-connect','ws-connect','start'].includes(x)),['unlock','avatar-connect','ws-connect','start']);
  assert.equal(starts[0].playback_mode,'avatar_webrtc');assert(!('max_turns' in starts[0]));
  callbacks.onEvent({type:'state',session_id:'ws',turn_id:1,data:{state:'LISTENING'}});
  ns=render();assert(button(ns,'primary').props.disabled);assert(!button(ns,'danger').props.disabled);
  button(ns,'danger').props.onClick();button(ns,'danger').props.onClick();assert.equal(stops,1);
  callbacks.onEvent({type:'session_stopped',session_id:'ws',turn_id:8,data:{reason:'client_stop'}});
  ns=render();assert(!button(ns,'primary').props.disabled);
  checks.push('single click: gesture unlock before awaits; avatar -> session_ready -> start; duplicate click rejected; one stop; UI resets');
  ns.find(n=>n.type==='select').props.onChange({target:{value:'browser'}});ns=render();trace=[];
  button(ns,'primary').props.onClick();await flush();assert.equal(starts.at(-1).playback_mode,'browser');assert(!trace.includes('avatar-connect')&&!trace.includes('unlock'));
  button(render(),'danger').props.onClick();callbacks.onEvent({type:'session_stopped',session_id:'ws',turn_id:9,data:{}});
  ns=render();ns.find(n=>n.type==='select').props.onChange({target:{value:'avatar_webrtc'}});ns=render();
  failSound=true;const before=starts.length;button(ns,'primary').props.onClick();await flush();assert.equal(starts.length,before);
  checks.push('WAV fallback still starts; sound permission denial never starts capture');
  failSound=false;slow=true;button(render(),'primary').props.onClick();await flush();button(render(),'danger').props.onClick();resolveAvatar();await flush();assert.equal(starts.length,before);
  checks.push('cancel during asynchronous avatar connection cannot send late start');
  slow=false;slowSound=true;button(render(),'primary').props.onClick();await flush();button(render(),'danger').props.onClick();await flush();assert(!button(render(),'primary').props.disabled);resolveSound();await flush();assert.equal(starts.length,before);
  checks.push('cancel releases UI even when initial audio permission promise is pending');
}
async function mediaContracts(){
  global.MediaStream=class {getTracks(){return [];}};
  const {AvatarClient}=load('frontend/src/lib/avatar-client.ts');
  const trace=[];let released=0;
  const track={stop(){released++;}};
  const video={muted:true,play(){trace.push('play');return Promise.resolve();},pause(){},srcObject:null};
  const context={sampleRate:48000,createMediaStreamDestination(){return {stream:{getTracks:()=>[track]}};},createBuffer:()=>({}),createBufferSource:()=>({connect(){},start(){trace.push('silent-start');},stop(){},disconnect(){}})};
  const client=new AvatarClient(video,{status(){},error(){},stats(){},feedback(){}});
  const ready=client.unlockSound(context);assert.deepEqual(trace,['silent-start','play']);assert.equal(video.muted,false);await ready;assert(client.hasSoundPermission());
  client.disconnect();assert.equal(released,1);assert.equal(video.srcObject,null);assert(!client.hasSoundPermission());
  checks.push('actual media client primes same element within gesture; local silent track disposed on disconnect');
}
function socketContracts(){
  let instance;const sent=[];let binaries=0;
  global.WebSocket=class {static OPEN=1;static CONNECTING=0;readyState=1;constructor(){instance=this;}send(v){sent.push(JSON.parse(v));}close(){}};
  const types=load('frontend/src/lib/types.ts');
  const {VoiceSocket}=load('frontend/src/lib/websocket.ts',{'./types':types});
  const socket=new VoiceSocket();socket.connect({onConnectionState(){},onEvent(){},onAudioBinary(){binaries++;},onError(m){throw Error(m);}});
  socket.sendStart({playback_mode:'avatar_webrtc',avatar_binding:{control_id:'c'}});
  assert.equal(sent[0].type,'start');assert(!('max_turns' in sent[0]));
  socket.sendBrowserPlaybackFinished(7,'audio');assert.equal(sent[1].type,'browser_playback_finished');
  instance.onmessage({data:new ArrayBuffer(4)});assert.equal(binaries,1);
  socket.sendStop();assert.equal(sent[2].type,'stop');socket.disconnect();
  checks.push('actual WebSocket serialization: unlimited start, browser WAV ACK/binary, explicit stop unchanged');
}
async function main(){await componentContracts();await mediaContracts();
  socketContracts();
  // Retain the existing media-flow / bounded completion contracts, but write to new evidence.
  const original=path.join(root,'scripts/stage6-frontend-contracts.cjs');
  const m=new Module(original,module);m.filename=original;m.paths=module.paths;
  const source=fs.readFileSync(original,'utf8').replace("'runtime/stage6/frontend-contracts.json'","'runtime/pre-freeze-productization/media-regression.json'");
  m._compile(source,original);await flush();
  assert.equal(JSON.parse(fs.readFileSync(path.join(out,'media-regression.json'))).status,'PASS');
  fs.writeFileSync(path.join(out,'ui-contracts.json'),JSON.stringify({status:'PASS',checks,real_models:0,real_voice_sessions:0},null,2));
  console.log('Productization UI/media contracts PASS');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
