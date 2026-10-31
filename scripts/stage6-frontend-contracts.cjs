// Pure Node mocks. This does not automate a browser or contact any endpoint.
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const source = path.join(root, 'frontend/src/lib/avatar-client.ts');
const compiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
let stopped = 0, closed = 0, eventsClosed = 0;
global.MediaStream = class { getTracks() { return []; } };
global.window = { devicePixelRatio: 1.5, visualViewport: { scale: 1 } };
global.fetch = async () => ({ ok: true, json: async () => ({ code: 0 }) });
let id = 0;
const timers = new Map();
global.setTimeout = (callback, ms) => { timers.set(++id, { callback, ms }); return id; };
global.clearTimeout = (key) => timers.delete(key);
const mod = new Module(source, module); mod.filename = source; mod.paths = module.paths; mod._compile(compiled, source);
const { AvatarClient } = mod.exports;
const feedback = [];
const video = { currentTime: 0, muted: true, paused: false, volume: 1, videoWidth: 1278, videoHeight: 720,
  getBoundingClientRect: () => ({ width: 582, height: 328 }), play: async () => {}, pause() { this.paused = true; }, srcObject: {}, cancelVideoFrameCallback() {} };
const client = new AvatarClient(video, { status() {}, error() {}, stats() {}, feedback: (kind, turn) => feedback.push({ kind, turn }) });
const binding = { control_id: 'control123', client_id: 'client123', sessionid: 'rtc123' };
const turn = { ...binding, ws_session_id: 'ws123', turn_id: 1, audio_id: 'audio123', bridge_turn_id: 'ws123:1', generation: 1, duration_seconds: 1 };
let audioBytes = 0, videoBytes = 0;
client.binding = binding; client.firstFrame = true;
client.events = { close() { eventsClosed++; } };
client.pc = { connectionState: 'connected', getStats: async () => new Map([
  ['audio', { type: 'inbound-rtp', kind: 'audio', bytesReceived: audioBytes += 200, totalAudioEnergy: 1, jitterBufferDelay: 1, jitterBufferEmittedCount: 10 }],
  ['video', { type: 'inbound-rtp', kind: 'video', timestamp: performance.now(), bytesReceived: videoBytes += 3000, frameWidth: 1278, frameHeight: 720, framesPerSecond: 25, framesDecoded: 20, packetsLost: 0, codecId: 'codec' }],
  ['codec', { mimeType: 'video/H264' }],
]), getReceivers: () => [{ track: { stop() { stopped++; } } }], close() { closed++; } };

async function main() {
  client.prepareTurn(turn);
  client.serverEvent({ sessionid: 'rtc123', turn_id: 'old', generation: 1, status: 'start' });
  if (client.serverStart !== 0) throw Error('Stale turn accepted');
  client.serverEvent({ sessionid: 'rtc123', turn_id: 'ws123:1', generation: 1, status: 'start' });
  video.currentTime = 2;
  await client.collectStats(client.epoch);
  if (feedback.length) throw Error('SSE or video.play alone fabricated audio start');
  await client.enableSound();
  await client.collectStats(client.epoch);
  if (feedback.length !== 1 || feedback[0].kind !== 'started') throw Error('Media-flow confirmation missing');
  client.serverEvent({ sessionid: 'rtc123', turn_id: 'ws123:1', generation: 99, status: 'end' });
  if (client.serverEnd) throw Error('Stale generation accepted');
  client.serverEvent({ sessionid: 'rtc123', turn_id: 'ws123:1', generation: 1, status: 'end' });
  if (feedback.length !== 1) throw Error('SSE end falsely completed browser playback');
  await client.collectStats(client.epoch);
  const ending = timers.get(client.finishTimer);
  if (!ending || turn.completion_margin_ms < 350 || turn.completion_margin_ms > 2000) throw Error('Unbounded playback-tail estimate');
  ending.callback();
  if (feedback.at(-1).kind !== 'estimated_finished' || client.pending) throw Error('Wrong finish semantics');
  client.disconnect();
  if (!stopped || !closed || !eventsClosed || video.srcObject !== null || !video.muted) throw Error('Cleanup left live resources');
  fs.writeFileSync(path.join(root, 'runtime/stage6/frontend-contracts.json'), JSON.stringify({ status: 'PASS', real_browser_actions: 0, real_tts_requests: 0, checks: ['stale-turn','sound-permission','actual-media-flow','stale-generation','SSE-end-not-browser-end','bounded-tail-estimate','close-tracks-peer-SSE-srcObject'] }, null, 2));
  console.log('Frontend media-state contracts PASS');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
