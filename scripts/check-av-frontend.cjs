// Reuse media-state contracts without overwriting historical Stage evidence.
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'runtime/av-stutter-investigation/offline');
fs.mkdirSync(out, { recursive: true });
let source = fs.readFileSync(path.join(__dirname, 'stage6-frontend-contracts.cjs'), 'utf8');
source = source.replace("'runtime/stage6/frontend-contracts.json'", "'runtime/av-stutter-investigation/offline/frontend-contracts.json'");
source = source.replace('const feedback = [];', 'const feedback = []; const diagnosticSamples = [];');
source = source.replace('stats() {}', 'stats(m) { diagnosticSamples.push(m); }');
source = source.replace('  client.disconnect();', `
  if (!diagnosticSamples.every(m => typeof m.monotonic_ms === 'number')) throw Error('No browser monotonic samples');
  if (!diagnosticSamples.some(m => typeof m.audio_bytesReceived_delta === 'number')) throw Error('No interval counters');
  client.previousVideo = {bytes: 999999, time: -1};
  await client.collectStats(client.epoch);
  if (diagnosticSamples.at(-1).video_bitrate_bps < 0) throw Error('Counter reset produced negative bitrate');
  client.disconnect();
  if (client.previousVideo !== null || client.previousDiagnostics !== null) throw Error('Reconnect retains old stream counters');
`);
const test = new Module(__filename, module);
test.filename = __filename; test.paths = module.paths;
test._compile(source, __filename);
