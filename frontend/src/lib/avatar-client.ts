export const AVATAR_CONTROL_URL = "http://127.0.0.1:8011";
export type AvatarBinding = { control_id: string; client_id: string; sessionid: string };
export type AvatarTurn = { ws_session_id: string; turn_id: number; audio_id: string; bridge_turn_id: string; generation?: number; duration_seconds: number; sessionid: string; control_id: string; completion_margin_ms?: number };
export type AvatarEvent = { status: string; turn_id: string; generation: number; sessionid: string };
export type AvatarFeedback = "started" | "estimated_finished" | "cancelled" | "error";
type Callbacks = { status: (status: string) => void; error: (message: string) => void; stats: (stats: Record<string, unknown>) => void; feedback: (kind: AvatarFeedback, turn: AvatarTurn) => void };

export class AvatarClient {
  private pc: RTCPeerConnection | null = null;
  private stream = new MediaStream();
  private binding: AvatarBinding | null = null;
  private events: EventSource | null = null;
  private epoch = 0;
  private frameId: number | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private firstFrame = false;
  private soundAllowed = false;
  private pending: AvatarTurn | null = null;
  private pendingEvents: AvatarEvent[] = [];
  private serverStart = 0;
  private serverEnd = 0;
  private started = false;
  private finishing = false;
  private armTime = 0;
  private audioBytesAtArm = 0;
  private lastAudioBytes = 0;
  private previousVideo: { bytes: number; time: number } | null = null;
  private previousDiagnostics: { time: number; media: number; counters: Record<string, number> } | null = null;
  private presentationFrameId: number | null = null;
  private presentation = { callbacks: 0, previousMs: 0, maxGapMs: 0, presentedFrames: 0 };
  private lastJitterSeconds = 0;
  private finishTimer: ReturnType<typeof setTimeout> | null = null;
  private statsBusy = false;
  private telemetryTick = 0;
  private turnTimeout: ReturnType<typeof setTimeout> | null = null;
  private frameCleanup: (() => void) | null = null;
  private lastFeedback = "none";
  private recorder: MediaRecorder | null = null;
  private recordedPreview = false;
  private recordingTurn: AvatarTurn | null = null;
  private recordingTimer: ReturnType<typeof setTimeout> | null = null;
  private capturedSpeech = false;
  private unlockStream: MediaStream | null = null;
  private unlockSource: AudioBufferSourceNode | null = null;

  // Call synchronously from the user's click, before any network awaits. A
  // local silent track starts this same media element with sound permitted.
  async unlockSound(context: AudioContext): Promise<void> {
    const epoch = this.epoch;
    const destination = context.createMediaStreamDestination();
    const source = context.createBufferSource();
    source.buffer = context.createBuffer(1, 128, context.sampleRate);
    source.loop = true; source.connect(destination); source.start();
    this.unlockStream = destination.stream; this.unlockSource = source;
    this.video.srcObject = destination.stream; this.video.muted = false;
    try {
      await this.video.play();
      if (epoch !== this.epoch) throw new Error("连接已取消。");
      this.soundAllowed = true;
    } catch {
      this.releaseUnlockTrack();
      throw new Error("浏览器未允许声音播放，请允许声音后再次点击连接。");
    }
  }

  private releaseUnlockTrack(): void {
    this.unlockSource?.stop(); this.unlockSource?.disconnect(); this.unlockSource = null;
    this.unlockStream?.getTracks().forEach((track) => track.stop()); this.unlockStream = null;
  }

  private capturePreviewFrame(label: 'idle' | 'speaking', turn?: AvatarTurn): void {
    const binding = this.binding;
    if (!binding || this.video.videoWidth !== 1278 || this.video.videoHeight !== 720) return;
    const canvas = document.createElement('canvas'); canvas.width = 1278; canvas.height = 720;
    canvas.getContext('2d')?.drawImage(this.video, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const form = new FormData();
      Object.entries(binding).forEach(([key, value]) => form.append(key, value));
      form.append('label', label); if (turn) form.append('audio_id', turn.audio_id);
      form.append('file', blob, label + '.png');
      void fetch(AVATAR_CONTROL_URL + '/frame', { method: 'POST', body: form }).catch(() => {});
    }, 'image/png');
  }

  private startPreviewRecording(): void {
    const mime = 'video/webm;codecs=vp8,opus';
    if (typeof MediaRecorder === 'undefined' || this.recordedPreview || !MediaRecorder.isTypeSupported(mime)) return;
    this.recordedPreview = true;
    const binding = this.binding;
    const chunks: BlobPart[] = [];
    const recorder = new MediaRecorder(this.stream, { mimeType: mime, videoBitsPerSecond: 8_000_000, audioBitsPerSecond: 128_000 });
    this.recorder = recorder;
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = () => {
      if (this.recordingTimer) clearTimeout(this.recordingTimer);
      const turn = this.recordingTurn;
      if (!binding || !turn || !chunks.length) return;
      const form = new FormData();
      Object.entries(binding).forEach(([key, value]) => form.append(key, value));
      form.append('audio_id', turn.audio_id); form.append('turn_id', String(turn.turn_id));
      form.append('file', new Blob(chunks, { type: 'video/webm' }), 'avatar-preview.webm');
      void fetch(AVATAR_CONTROL_URL + '/recording', { method: 'POST', body: form }).catch(() => {});
    };
    recorder.start(500);
    this.recordingTimer = setTimeout(() => { if (recorder.state !== 'inactive') recorder.stop(); }, 30000);
  }

  private stopPreviewRecording(): void {
    if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop();
    this.recorder = null;
  }

  private notifyFeedback(kind: AvatarFeedback, turn: AvatarTurn): void {
    this.lastFeedback = kind;
    this.callbacks.feedback(kind, turn);
    if (this.binding) void this.api('/feedback', { ...this.binding, ...turn, kind, completion_semantics: 'bounded_media_estimate' }).catch(() => {});
  }

  constructor(private video: HTMLVideoElement, private callbacks: Callbacks) {}
  getBinding(): AvatarBinding | null { return this.binding; }
  isReady(): boolean { return this.firstFrame && this.pc?.connectionState === "connected"; }
  hasSoundPermission(): boolean { return this.soundAllowed && !this.video.muted; }
  isIdle(): boolean { return this.pending === null; }

  private async api(path: string, data: Record<string, unknown>, timeout = 15000): Promise<Record<string, unknown>> {
    const response = await fetch(AVATAR_CONTROL_URL + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data), signal: AbortSignal.timeout(timeout) });
    const result = await response.json();
    if (!response.ok || result.code !== 0) throw new Error(result.message ?? "数字人接口未完成操作。");
    return result;
  }

  async connect(): Promise<void> {
    if (this.pc) return;
    const epoch = ++this.epoch;
    this.previousVideo = null; this.previousDiagnostics = null;
    this.lastAudioBytes = 0; this.audioBytesAtArm = 0; this.lastJitterSeconds = 0;
    this.presentation = { callbacks: 0, previousMs: 0, maxGapMs: 0, presentedFrames: 0 };
    this.callbacks.status("正在连接数字人…");
    const pc = new RTCPeerConnection({ iceServers: [] });
    this.pc = pc;
    this.stream = new MediaStream();
    this.video.srcObject = this.stream;
    this.video.muted = !this.soundAllowed;
    this.releaseUnlockTrack();
    this.firstFrame = false;
    const clientId = crypto.randomUUID().replaceAll("-", "");
    try {
      pc.addTransceiver("audio", { direction: "recvonly" });
      pc.addTransceiver("video", { direction: "recvonly" });
      pc.ontrack = ({ track }) => {
        if (this.epoch !== epoch) { track.stop(); return; }
        this.stream.addTrack(track);
        track.onended = () => { if (this.epoch === epoch) this.fail("数字人媒体轨道已结束，请重新连接。"); };
        void this.video.play().catch(() => { if (epoch === this.epoch) this.fail("浏览器未允许媒体播放，请允许声音后重新连接。"); });
      };
      pc.onconnectionstatechange = () => {
        if (this.epoch === epoch && ["failed", "closed", "disconnected"].includes(pc.connectionState)) this.fail("数字人连接已断开。");
      };
      await pc.setLocalDescription(await pc.createOffer());
      if (pc.iceGatheringState !== "complete") await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => { pc.removeEventListener("icegatheringstatechange", changed); reject(new Error("本机媒体候选收集超时。")); }, 8000);
        const changed = () => { if (pc.iceGatheringState === "complete") { clearTimeout(timeout); pc.removeEventListener("icegatheringstatechange", changed); resolve(); } };
        pc.addEventListener("icegatheringstatechange", changed);
      });
      const answer = await this.api("/connect", { client_id: clientId, type: "offer", sdp: pc.localDescription?.sdp }, 90000);
      const binding = { client_id: clientId, control_id: String(answer.control_id), sessionid: String(answer.sessionid) };
      if (this.epoch !== epoch) { void this.api("/disconnect", binding).catch(() => {}); return; }
      this.binding = binding;
      await pc.setRemoteDescription({ type: "answer", sdp: String(answer.sdp) });
      this.events = new EventSource(`${AVATAR_CONTROL_URL}/events?control_id=${binding.control_id}&client_id=${clientId}`);
      this.events.onmessage = ({ data }) => { if (epoch === this.epoch) this.serverEvent(JSON.parse(data) as AvatarEvent); };
      this.events.onerror = () => { if (epoch === this.epoch) this.fail("数字人状态连接中断，请重新连接。"); };
      await this.waitForFrame(epoch);
      if (epoch !== this.epoch) return;
      if (this.video.requestVideoFrameCallback) {
        const presented = (now: number, metadata: VideoFrameCallbackMetadata) => {
          if (epoch !== this.epoch) return;
          const p = this.presentation;
          if (p.previousMs) p.maxGapMs = Math.max(p.maxGapMs, now - p.previousMs);
          p.previousMs = now; p.callbacks++; p.presentedFrames = metadata.presentedFrames;
          this.presentationFrameId = this.video.requestVideoFrameCallback(presented);
        };
        this.presentationFrameId = this.video.requestVideoFrameCallback(presented);
      }
      await this.api("/ready", { ...binding, first_frame: true, width: this.video.videoWidth, height: this.video.videoHeight, client_kind: "browser" });
      this.callbacks.status("数字人画面已就绪");
      this.timer = setInterval(() => { void this.collectStats(epoch); }, 500);
    } catch (error) {
      if (epoch === this.epoch) this.fail(error instanceof Error ? error.message : "数字人连接失败。");
      throw error;
    }
  }

  private waitForFrame(epoch: number): Promise<void> {
    return new Promise((resolve, reject) => {
      let loaded: (() => void) | null = null;
      const cleanup = () => { clearTimeout(timeout); if (loaded) this.video.removeEventListener('loadeddata', loaded); };
      const timeout = setTimeout(() => { cleanup(); reject(new Error("连接已建立，但实际视频帧未在30秒内到达。")); }, 30000);
      this.frameCleanup = () => { cleanup(); reject(new Error('连接已取消。')); };
      const frame = () => {
        if (epoch !== this.epoch) { clearTimeout(timeout); reject(new Error("连接已取消。")); return; }
        if (this.video.videoWidth > 0 && this.video.videoHeight > 0 && this.video.readyState >= 2) {
          this.firstFrame = true;
          cleanup(); this.frameCleanup = null;
          resolve();
          return;
        }
        if (this.video.requestVideoFrameCallback) this.frameId = this.video.requestVideoFrameCallback(frame);
      };
      if (typeof this.video.requestVideoFrameCallback === "function") this.frameId = this.video.requestVideoFrameCallback(frame);
      else {
        const ready = () => { this.video.removeEventListener("loadeddata", ready); frame(); };
        loaded = ready;
        this.video.addEventListener("loadeddata", ready, { once: true });
        if (this.video.readyState >= 2) ready();
      }
    });
  }

  async enableSound(): Promise<void> {
    if (!this.isReady()) throw new Error("请先连接数字人并等待画面。");
    this.video.muted = false;
    try {
      await this.video.play();
      this.soundAllowed = true;
      this.callbacks.status("播放器声音已启用");
    } catch {
      this.video.muted = true;
      this.soundAllowed = false;
      throw new Error("浏览器阻止声音播放，请允许声音后重新连接。");
    }
  }

  prepareTurn(turn: AvatarTurn): void {
    if (!this.binding || turn.control_id !== this.binding.control_id || turn.sessionid !== this.binding.sessionid) throw new Error("数字人会话不匹配。");
    if (this.pending && this.pending.audio_id !== turn.audio_id) throw new Error("上一轮播放流程尚未结束。");
    if (!this.pending) {
      this.pending = turn; this.serverStart = 0; this.serverEnd = 0; this.started = false; this.finishing = false;
      this.armTime = this.video.currentTime; this.audioBytesAtArm = this.lastAudioBytes;
    } else this.pending = { ...this.pending, ...turn };
    if (this.pending.generation !== undefined) {
      if (this.turnTimeout) clearTimeout(this.turnTimeout);
      const current = this.pending;
      this.turnTimeout = setTimeout(() => { if (this.pending?.audio_id === current.audio_id) this.fail('本轮媒体状态超时，已断开，请重新连接。'); }, Math.min(90000, current.duration_seconds * 1000 + 20000));
      const buffered = this.pendingEvents; this.pendingEvents = [];
      buffered.forEach((event) => this.serverEvent(event));
    }
  }

  private serverEvent(event: AvatarEvent): void {
    const turn = this.pending;
    if (!turn || event.sessionid !== turn.sessionid || event.turn_id !== turn.bridge_turn_id) return;
    if (turn.generation === undefined) { if (this.pendingEvents.length < 8) this.pendingEvents.push(event); return; }
    if (event.generation !== turn.generation) return;
    if (event.status === "start") { this.serverStart = performance.now(); this.callbacks.status("服务端音频已开始，正在确认播放器流程"); }
    if (event.status === "end") { this.serverEnd = performance.now(); this.callbacks.status("服务端已发送完音频 · 等待播放缓冲"); }
  }

  async preview(turnId: number): Promise<void> {
    const binding = this.binding;
    if (!binding || !this.isReady() || !this.hasSoundPermission()) throw new Error("请连接数字人并开启声音。");
    const wsId = `preview-${binding.client_id}`;
    this.prepareTurn({ ...binding, ws_session_id: wsId, turn_id: turnId, audio_id: `pending-preview-${turnId}`, bridge_turn_id: `${wsId}:${turnId}`, duration_seconds: 0 });
    this.capturePreviewFrame('idle');
    this.startPreviewRecording();
    let result: Record<string, unknown>;
    try { result = await this.api("/preview", { ...binding, turn_id: turnId }, 210000); }
    catch (error) { this.fail(error instanceof Error ? error.message : '短句提交失败。'); throw error; }
    const turn = result.data as AvatarTurn;
    // Preview's server-issued audio_id replaces the provisional local one.
    if (this.pending?.bridge_turn_id === turn.bridge_turn_id) this.pending = { ...this.pending, audio_id: turn.audio_id };
    this.prepareTurn(turn);
    this.recordingTurn = turn;
  }

  private async collectStats(epoch: number): Promise<void> {
    if (!this.pc || this.statsBusy) return;
    this.statsBusy = true;
    try {
      const report = await this.pc.getStats();
      if (epoch !== this.epoch) return;
      const metrics: Record<string, unknown> = { width: this.video.videoWidth, height: this.video.videoHeight, displayed_width: this.video.getBoundingClientRect().width, displayed_height: this.video.getBoundingClientRect().height, device_pixel_ratio: window.devicePixelRatio, zoom_scale: window.visualViewport?.scale, media_time: this.video.currentTime, paused: this.video.paused, muted: this.video.muted, sound_permission: this.soundAllowed };
      Object.assign(metrics, { wall_time_ms: Date.now(), pending_turn: this.pending?.bridge_turn_id, generation: this.pending?.generation, server_start_received: !!this.serverStart, server_end_received: !!this.serverEnd, last_feedback: this.lastFeedback });
      const diagnosticNow = performance.now();
      const counters: Record<string, number> = {};
      Object.assign(metrics, { monotonic_ms: diagnosticNow, ready_state: this.video.readyState, network_state: this.video.networkState, ended: this.video.ended, playback_rate: this.video.playbackRate, visibility: typeof document !== 'undefined' ? document.visibilityState : 'unknown' });
      const quality = this.video.getVideoPlaybackQuality?.();
      if (quality) Object.assign(metrics, { playback_total_frames: quality.totalVideoFrames, playback_dropped_frames: quality.droppedVideoFrames });
      if (this.presentationFrameId !== null) {
        Object.assign(metrics, { render_callbacks: this.presentation.callbacks, presented_frames: this.presentation.presentedFrames, render_gap_max_ms: this.presentation.maxGapMs, render_silence_ms: this.presentation.previousMs ? diagnosticNow - this.presentation.previousMs : undefined });
        this.presentation.maxGapMs = 0;
      }
      report.forEach((stat) => {
        if (stat.type !== "inbound-rtp") return;
        if (stat.kind === 'audio' || stat.kind === 'video') {
          // Preserve cumulative values and interval deltas. Missing browser
          // fields stay absent; unsupported counters are never reported as zero.
          for (const field of ['bytesReceived', 'packetsReceived', 'packetsLost', 'jitter', 'jitterBufferDelay', 'jitterBufferEmittedCount', 'concealedSamples', 'silentConcealedSamples', 'concealmentEvents', 'totalSamplesReceived', 'insertedSamplesForDeceleration', 'removedSamplesForAcceleration', 'framesReceived', 'framesDecoded', 'framesDropped', 'freezeCount', 'totalFreezesDuration', 'totalDecodeTime', 'totalProcessingDelay']) {
            if (typeof stat[field] === 'number') { const key = `${stat.kind}_${field}`; counters[key] = stat[field]; metrics[key] = stat[field]; }
          }
        }
        if (stat.kind === "audio") {
          this.lastAudioBytes = stat.bytesReceived ?? 0;
          this.lastJitterSeconds = stat.jitterBufferEmittedCount > 0 ? stat.jitterBufferDelay / stat.jitterBufferEmittedCount : 0;
          metrics.audio_bytes = this.lastAudioBytes; metrics.audio_energy = stat.totalAudioEnergy; metrics.jitter_buffer_seconds = this.lastJitterSeconds;
        }
        if (stat.kind === "video") {
          metrics.received_width = stat.frameWidth; metrics.received_height = stat.frameHeight; metrics.fps = stat.framesPerSecond; metrics.frames_decoded = stat.framesDecoded; metrics.packets_lost = stat.packetsLost;
          const codec = report.get(stat.codecId); metrics.codec = codec?.mimeType;
          const now = stat.timestamp; const bytes = stat.bytesReceived ?? 0;
          if (this.previousVideo && now > this.previousVideo.time && bytes >= this.previousVideo.bytes) metrics.video_bitrate_bps = (bytes - this.previousVideo.bytes) * 8000 / (now - this.previousVideo.time);
          this.previousVideo = { bytes, time: now };
        }
      });
      const previous = this.previousDiagnostics;
      if (previous && diagnosticNow > previous.time) {
        metrics.sample_interval_ms = diagnosticNow - previous.time;
        metrics.media_time_delta = this.video.currentTime - previous.media;
        for (const [key, value] of Object.entries(counters)) {
          if (key in previous.counters && value >= previous.counters[key] && !key.endsWith('_jitter')) metrics[`${key}_delta`] = value - previous.counters[key];
        }
      }
      this.previousDiagnostics = { time: diagnosticNow, media: this.video.currentTime, counters };
      this.callbacks.stats(metrics);
      const turn = this.pending;
      if (turn && this.serverStart && this.soundAllowed && !this.video.muted && !this.video.paused && this.video.currentTime > this.armTime && this.lastAudioBytes > this.audioBytesAtArm && !this.started) {
        this.started = true;
        this.notifyFeedback("started", turn);
        if (this.recordedPreview && !this.capturedSpeech) { this.capturedSpeech = true; this.capturePreviewFrame('speaking', turn); }
        this.callbacks.status("音轨数据已进入播放器流程");
      }
      if (turn && this.started && this.serverEnd && !this.finishing) {
        this.finishing = true;
        const marginMs = Math.min(2000, Math.max(350, this.lastJitterSeconds * 1000 + 250));
        turn.completion_margin_ms = marginMs;
        const waitMs = Math.max(0, this.serverStart + turn.duration_seconds * 1000 - performance.now()) + marginMs;
        this.finishTimer = setTimeout(() => {
          if (epoch !== this.epoch || this.pending?.audio_id !== turn.audio_id) return;
          this.pending = null;
          if (this.turnTimeout) clearTimeout(this.turnTimeout);
          this.notifyFeedback("estimated_finished", turn);
          this.stopPreviewRecording();
          this.callbacks.status("本轮播放流程估计结束");
        }, waitMs);
      }
      if (this.binding && ++this.telemetryTick % 4 === 0) await this.api("/telemetry", { ...this.binding, metrics });
    } catch (error) { if (epoch === this.epoch) this.callbacks.error(error instanceof Error ? error.message : "媒体统计读取失败。"); }
    finally { this.statsBusy = false; }
  }

  private fail(message: string): void { this.callbacks.error(message); this.disconnect(); }
  disconnect(): void {
    ++this.epoch;
    this.previousVideo = null; this.previousDiagnostics = null;
    if (this.presentationFrameId !== null && this.video.cancelVideoFrameCallback) this.video.cancelVideoFrameCallback(this.presentationFrameId);
    this.presentationFrameId = null;
    if (this.pending) this.notifyFeedback("cancelled", this.pending);
    this.pending = null; this.pendingEvents = [];
    if (this.timer) clearInterval(this.timer);
    if (this.finishTimer) clearTimeout(this.finishTimer);
    if (this.turnTimeout) clearTimeout(this.turnTimeout);
    this.stopPreviewRecording();
    this.frameCleanup?.(); this.frameCleanup = null;
    if (this.frameId !== null && this.video.cancelVideoFrameCallback) this.video.cancelVideoFrameCallback(this.frameId);
    this.events?.close(); this.events = null;
    this.video.muted = true; this.video.pause(); this.soundAllowed = false;
    this.releaseUnlockTrack();
    this.pc?.getReceivers().forEach((receiver) => receiver.track?.stop());
    this.stream.getTracks().forEach((track) => track.stop());
    if (this.pc) this.pc.onconnectionstatechange = null;
    this.pc?.close(); this.pc = null; this.video.srcObject = null; this.firstFrame = false;
    const binding = this.binding; this.binding = null;
    if (binding) void fetch(AVATAR_CONTROL_URL + "/disconnect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(binding), keepalive: true }).catch(() => {});
    this.callbacks.status("数字人已断开");
  }
}
