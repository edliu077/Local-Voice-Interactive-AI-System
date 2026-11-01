"use client";

import { useEffect, useRef, useState } from "react";
import { AvatarVideo, type AvatarVideoHandle } from "@/components/AvatarVideo";
import type { AvatarFeedback, AvatarTurn } from "@/lib/avatar-client";
import {
  EXPRESSION_NAMES,
  expressionController,
  type DirectParameterDiagnostic,
  type ExpressionName,
  type ExpressionParameterSnapshot,
  type ExpressionParameterStates,
  type ExpressionRuntimeDiagnostic,
} from "@/lib/expression-controller";
import { mouthController } from "@/lib/mouth-controller";
import { VoiceSocket } from "@/lib/websocket";
import type { AssistantEmotion, ConnectionState, ConversationEntry, VoiceState, WsEvent } from "@/lib/types";

const STATE_LABELS: Record<VoiceState, string> = {
  IDLE: "待机",
  LISTENING: "正在听你说话…",
  TRANSCRIBING: "正在识别…",
  THINKING: "正在思考…",
  SYNTHESIZING: "正在准备声音…",
  SPEAKING: "正在说话…",
  ERROR: "发生错误",
};

const SHOW_DEV_EXPRESSION_TESTS = false;

type PendingBrowserAudio = {
  audioId: string;
  turnId: number;
  byteLength: number;
};

type PendingEmotion = {
  turnId: number;
  emotion: AssistantEmotion;
};

const EMOTION_TO_EXPRESSION = {
  love: "aixin",
  sad: "kuku",
  excited: "xingxing",
} as const;

function textValue(data: Record<string, unknown>, key: string): string | null {
  const value = data[key];
  return typeof value === "string" ? value : null;
}

function stateValue(data: Record<string, unknown>): VoiceState | null {
  const value = textValue(data, "state");
  return value && value in STATE_LABELS ? value as VoiceState : null;
}

function assistantEmotionValue(data: Record<string, unknown>): AssistantEmotion {
  const value = textValue(data, "emotion");
  return value === "love" || value === "sad" || value === "excited" || value === "neutral" ? value : "neutral";
}

export function VoiceConsole() {
  const avatarRef = useRef<AvatarVideoHandle | null>(null);
  const wsSessionRef = useRef<string | null>(null);
  const socketRef = useRef<VoiceSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const activeSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const pendingBrowserAudioRef = useRef<PendingBrowserAudio | null>(null);
  const activeBrowserAudioRef = useRef<PendingBrowserAudio | null>(null);
  const browserPlaybackCancelledRef = useRef(false);
  const pendingEmotionRef = useRef<PendingEmotion | null>(null);
  const playbackModeRef = useRef("avatar_webrtc");
  const lipSyncFrameRef = useRef<number | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("disconnected");
  const [connecting, setConnecting] = useState(false);
  const connectingRef = useRef(false);
  const endingRef = useRef(false);
  const connectionEpoch = useRef(0);
  const cancelVoiceConnect = useRef<(() => void) | null>(null);
  const cancelPreparation = useRef<(() => void) | null>(null);
  const [playbackMode, setPlaybackMode] = useState("avatar_webrtc");
  const [activeConversation, setActiveConversation] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>("IDLE");
  const [currentUser, setCurrentUser] = useState("");
  const [currentAssistant, setCurrentAssistant] = useState("");
  const [history, setHistory] = useState<ConversationEntry[]>([]);
  const [activity, setActivity] = useState("等待连接本机语音服务");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [expressionTestStatus, setExpressionTestStatus] = useState<string | null>(null);
  const [selectedExpressionName, setSelectedExpressionName] = useState<ExpressionName | null>(null);
  const [expressionParameterSnapshot, setExpressionParameterSnapshot] = useState<ExpressionParameterSnapshot | null>(null);
  const [expressionParameterStates, setExpressionParameterStates] = useState<ExpressionParameterStates | null>(null);
  const [expressionDiagnostic, setExpressionDiagnostic] = useState<ExpressionRuntimeDiagnostic | null>(null);
  const [directParameterDiagnostic, setDirectParameterDiagnostic] = useState<DirectParameterDiagnostic | null>(null);

  useEffect(() => () => {
    ++connectionEpoch.current;
    cancelPreparation.current?.();
    cancelVoiceConnect.current?.();
    browserPlaybackCancelledRef.current = true;
    stopLipSync();
    resetExpressionLifecycle();
    activeSourceRef.current?.stop();
    avatarRef.current?.disconnect();
    socketRef.current?.disconnect();
  }, []);

  function appendHistory(entry: ConversationEntry): void {
    setHistory((previous) => [...previous, entry].slice(-12));
  }

  function resetExpressionLifecycle(turnId?: number): void {
    expressionController.reset();
    if (turnId === undefined || pendingEmotionRef.current?.turnId === turnId) {
      pendingEmotionRef.current = null;
    }
  }

  function applyPendingEmotion(turnId: number): void {
    const pending = pendingEmotionRef.current;
    if (!pending || pending.turnId !== turnId || pending.emotion === "neutral") {
      resetExpressionLifecycle(turnId);
      return;
    }
    const expressionName = EMOTION_TO_EXPRESSION[pending.emotion];
    void expressionController.apply(expressionName).then((applied) => {
      if (!applied) resetExpressionLifecycle(turnId);
    }).catch(() => {
      resetExpressionLifecycle(turnId);
    });
  }

  async function runDevExpressionTest(name: "neutral" | ExpressionName): Promise<void> {
    if (name === "neutral") {
      expressionController.reset();
      setExpressionTestStatus("neutral reset requested");
      setSelectedExpressionName(null);
      setExpressionParameterSnapshot(null);
      setExpressionParameterStates(expressionController.resetAllParameters());
      setExpressionDiagnostic(null);
      setDirectParameterDiagnostic(null);
      return;
    }
    setSelectedExpressionName(name);
    setExpressionTestStatus(`${name}: direct apply requested`);
    setExpressionParameterSnapshot(expressionController.readParameter(name));
    const applied = await expressionController.apply(name);
    setExpressionParameterStates(expressionController.readAllParameters());
    setExpressionDiagnostic(null);
    setDirectParameterDiagnostic(null);
    setExpressionTestStatus(applied ? `${name}: direct apply complete` : `${name}: direct apply failed; neutral reset requested`);
  }

  async function runNamedExpressionDiagnostic(): Promise<void> {
    if (!selectedExpressionName) {
      setExpressionTestStatus("select a named expression before running the named API diagnostic");
      return;
    }
    setExpressionTestStatus(`${selectedExpressionName}: named API diagnostic started`);
    const diagnostic = await expressionController.diagnose(selectedExpressionName);
    setExpressionDiagnostic(diagnostic);
    setExpressionParameterStates(expressionController.readAllParameters());
    setExpressionTestStatus(diagnostic
      ? `${selectedExpressionName}: model.expression ${diagnostic.expressionApiStatus}`
      : `${selectedExpressionName}: named API diagnostic failed`);
  }

  function readSelectedExpressionParameter(): void {
    if (!selectedExpressionName) return;
    const snapshot = expressionController.readParameter(selectedExpressionName);
    setExpressionParameterSnapshot(snapshot);
    setExpressionParameterStates(expressionController.readAllParameters());
    setExpressionTestStatus(snapshot ? `${selectedExpressionName}: parameter read` : `${selectedExpressionName}: parameter read failed`);
  }

  async function runDirectParameterTest(): Promise<void> {
    if (!selectedExpressionName) {
      setExpressionTestStatus("select a named expression before running a direct parameter test");
      return;
    }
    const snapshot = expressionController.readParameter(selectedExpressionName);
    if (!snapshot) {
      setExpressionTestStatus(`${selectedExpressionName}: parameter read failed`);
      return;
    }
    setExpressionParameterSnapshot(snapshot);
    const diagnostic = await expressionController.setDirect(selectedExpressionName, 1);
    setDirectParameterDiagnostic(diagnostic);
    if (diagnostic) setExpressionParameterSnapshot(diagnostic.afterSeveralFrames);
    setExpressionParameterStates(expressionController.readAllParameters());
    setExpressionTestStatus(diagnostic ? `direct set requested for ${diagnostic.name}` : "direct parameter diagnostic failed");
  }

  function runDirectResetTest(): void {
    const states = expressionController.resetAllParameters();
    setExpressionParameterStates(states);
    setDirectParameterDiagnostic(null);
    setExpressionParameterSnapshot(selectedExpressionName ? states?.[selectedExpressionName] ?? null : null);
    setExpressionTestStatus(states ? "direct reset complete" : "direct reset failed");
  }

  function stopLipSync(): void {
    if (lipSyncFrameRef.current !== null) {
      cancelAnimationFrame(lipSyncFrameRef.current);
      lipSyncFrameRef.current = null;
    }
    mouthController.reset();
  }

  function startLipSync(analyser: AnalyserNode): void {
    stopLipSync();
    const samples = new Float32Array(analyser.fftSize);
    let current = 0;
    const tick = (): void => {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (let index = 0; index < samples.length; index += 1) sum += samples[index] * samples[index];
      const rms = Math.sqrt(sum / samples.length);
      const target = Math.min(1, Math.max(0, (rms - 0.018) * 7));
      current += (target - current) * (target > current ? 0.25 : 0.15);
      mouthController.value = current;
      lipSyncFrameRef.current = requestAnimationFrame(tick);
    };
    lipSyncFrameRef.current = requestAnimationFrame(tick);
  }

  function sendBrowserPlaybackError(pending: PendingBrowserAudio, code: string): void {
    try {
      socketRef.current?.sendAudioPlaybackError(pending.turnId, pending.audioId, code);
    } catch {
      // I0 also terminates a browser turn on disconnect or acknowledgement timeout.
    }
  }

  async function handleAudioBinary(audio: ArrayBuffer): Promise<void> {
    if (playbackModeRef.current === "avatar_webrtc") {
      pendingBrowserAudioRef.current = null;
      setErrorMessage("已阻止旧WAV播放：当前使用数字人音轨。");
      return;
    }
    const pending = pendingBrowserAudioRef.current;
    pendingBrowserAudioRef.current = null;
    if (!pending) {
      stopLipSync();
      resetExpressionLifecycle();
      setErrorMessage("收到未配对的音频数据。");
      return;
    }
    if (audio.byteLength !== pending.byteLength) {
      stopLipSync();
      resetExpressionLifecycle(pending.turnId);
      sendBrowserPlaybackError(pending, "binary_size_mismatch");
      setErrorMessage("音频数据大小校验失败。");
      return;
    }
    const context = audioContextRef.current;
    if (!context || context.state !== "running") {
      stopLipSync();
      resetExpressionLifecycle(pending.turnId);
      sendBrowserPlaybackError(pending, "audio_context_suspended");
      setErrorMessage("浏览器音频上下文未准备好。");
      return;
    }
    try {
      const decoded = await context.decodeAudioData(audio);
      if (browserPlaybackCancelledRef.current || playbackModeRef.current !== 'browser') {
        stopLipSync();
        resetExpressionLifecycle(pending.turnId);
        socketRef.current?.sendBrowserPlaybackCancelled(pending.turnId, pending.audioId);
        return;
      }
      const source = context.createBufferSource();
      const analyser = context.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0;
      source.buffer = decoded;
      source.connect(analyser);
      analyser.connect(context.destination);
      activeSourceRef.current = source;
      activeBrowserAudioRef.current = pending;
      source.onended = () => {
        stopLipSync();
        resetExpressionLifecycle(pending.turnId);
        if (activeSourceRef.current === source) activeSourceRef.current = null;
        if (activeBrowserAudioRef.current === pending) activeBrowserAudioRef.current = null;
        if (browserPlaybackCancelledRef.current) return;
        try {
          socketRef.current?.sendBrowserPlaybackFinished(pending.turnId, pending.audioId);
        } catch {
          // I0 releases its wait when the client disconnects.
        }
      };
      source.start();
      startLipSync(analyser);
      socketRef.current?.sendBrowserPlaybackStarted(pending.turnId, pending.audioId);
      setActivity("她正在通过浏览器扬声器说话");
    } catch {
      stopLipSync();
      resetExpressionLifecycle(pending.turnId);
      activeSourceRef.current?.stop();
      activeSourceRef.current = null;
      sendBrowserPlaybackError(pending, "decode_failed");
      setErrorMessage("浏览器无法解码或播放本机语音。");
    }
  }

  function handleEvent(event: WsEvent): void {
    const data = event.data as Record<string, unknown>;
    switch (event.type) {
      case "session_ready":
        wsSessionRef.current = event.session_id;
        setErrorMessage(null);
        setActivity("本机语音服务已准备好");
        break;
      case "state": {
        const nextState = stateValue(data);
        if (nextState) {
          setVoiceState(nextState);
          if (nextState === "LISTENING") resetExpressionLifecycle();
        }
        break;
      }
      case "speech_started":
        setActivity("检测到你开始说话");
        break;
      case "speech_ended":
        setActivity("已收到这句话，正在处理");
        break;
      case "user_transcript": {
        const text = textValue(data, "text");
        if (text) {
          setCurrentUser(text);
          appendHistory({ role: "user", text, turnId: event.turn_id });
        }
        break;
      }
      case "assistant_text": {
        const text = textValue(data, "text");
        if (text) {
          pendingEmotionRef.current = { turnId: event.turn_id, emotion: assistantEmotionValue(data) };
          setCurrentAssistant(text);
          appendHistory({ role: "assistant", text, turnId: event.turn_id });
        }
        break;
      }
      case "audio_ready": {
        if (data.transport === "avatar_webrtc") {
          if (playbackModeRef.current !== "avatar_webrtc") { setErrorMessage("播放模式不匹配，已拒绝数字人音轨。"); avatarRef.current?.disconnect(); break; }
          avatarRef.current?.prepare(data as unknown as AvatarTurn);
          setActivity("数字人音频已提交，等待播放器流程");
          break;
        }
        if (playbackModeRef.current === "avatar_webrtc") { pendingBrowserAudioRef.current = null; setErrorMessage("已阻止当前轮次的旧音频通道。"); break; }
        const duration = data.duration_seconds;
        if (data.transport === "websocket_binary") {
          const audioId = textValue(data, "audio_id");
          const byteLength = data.byte_length;
          if (!audioId || typeof byteLength !== "number" || byteLength <= 0) {
            setErrorMessage("浏览器音频元数据无效。");
            break;
          }
          pendingBrowserAudioRef.current = { audioId, turnId: event.turn_id, byteLength };
          setActivity(typeof duration === "number" ? `浏览器音频已准备（约 ${duration.toFixed(1)} 秒）` : "浏览器音频已准备");
        } else {
          setActivity(typeof duration === "number" ? `声音已准备（约 ${duration.toFixed(1)} 秒，由本机播放）` : "声音已准备（由本机播放）");
        }
        break;
      }
      case "avatar_audio_pending":
        if (playbackModeRef.current === "avatar_webrtc") avatarRef.current?.prepare(data as unknown as AvatarTurn);
        break;
      case "playback_started":
        applyPendingEmotion(event.turn_id);
        setActivity(playbackModeRef.current === "browser" ? "她正在通过浏览器扬声器说话" : "她正在通过本机扬声器说话");
        break;
      case "playback_finished":
        resetExpressionLifecycle(event.turn_id);
        setActivity(playbackModeRef.current === "avatar_webrtc" ? "本轮播放流程估计结束" : "播放完成");
        break;
      case "turn_complete":
        resetExpressionLifecycle(event.turn_id);
        setActivity(`第 ${event.turn_id} 轮已完成`);
        break;
      case "error":
        resetExpressionLifecycle();
        setErrorMessage(textValue(data, "message") ?? "本机语音服务发生错误。");
        setVoiceState("ERROR");
        break;
      case "session_stopped":
        resetExpressionLifecycle();
        setActiveConversation(false);
        setStopping(false);
        setVoiceState("IDLE");
        setActivity("本次对话已结束");
        break;
      default:
        break;
    }
  }

  function connect(): Promise<void> {
    socketRef.current?.disconnect();
    const socket = new VoiceSocket();
    socketRef.current = socket;
    return new Promise((resolve, reject) => {
      const finish = (error?: Error) => {
        clearTimeout(timeout);
        if (cancelVoiceConnect.current === cancel) cancelVoiceConnect.current = null;
        if (error) reject(error); else resolve();
      };
      const cancel = () => finish(new Error("连接已取消。"));
      const timeout = setTimeout(() => finish(new Error("语音服务准备超时，请确认本机服务已就绪。")), 30000);
      cancelVoiceConnect.current = cancel;
      socket.connect({
      onConnectionState: (nextConnection) => {
        if (socketRef.current !== socket) return;
        setConnection(nextConnection);
        if (nextConnection !== "connected") {
          stopLipSync();
          resetExpressionLifecycle();
          if (nextConnection !== "connecting") {
            finish(new Error("语音服务连接已断开。"));
            setActiveConversation(false); setStopping(false);
          }
        }
      },
      onEvent: (event) => {
        if (socketRef.current !== socket) return;
        handleEvent(event);
        if (event.type === "session_ready") finish();
      },
      onAudioBinary: (audio) => { if (socketRef.current === socket) void handleAudioBinary(audio); },
      onError: (message) => {
        if (socketRef.current !== socket) return;
        resetExpressionLifecycle();
        setErrorMessage(message);
        setConnection("error");
        finish(new Error(message));
      },
    });
    });
  }

  function disconnect(): void {
    endingRef.current = true;
    ++connectionEpoch.current;
    cancelPreparation.current?.();
    cancelVoiceConnect.current?.();
    avatarRef.current?.disconnect();
    stopLipSync();
    resetExpressionLifecycle();
    socketRef.current?.disconnect();
    setConnection("disconnected");
    setActiveConversation(false);
    setStopping(false);
    setVoiceState("IDLE");
    setActivity("已断开连接");
  }

  async function startConversation(): Promise<void> {
    if (connectingRef.current || activeConversation) return;
    connectingRef.current = true; setConnecting(true);
    const epoch = ++connectionEpoch.current;
    let rejectPreparation!: (error: Error) => void;
    const cancelled = new Promise<never>((_, reject) => { rejectPreparation = reject; });
    cancelPreparation.current = () => rejectPreparation(new Error("连接已取消。"));
    const preparationTimeout = setTimeout(() => rejectPreparation(new Error("连接准备超时，请确认本机服务就绪后重试。")), 180000);
    const waitFor = <T,>(operation: Promise<T>) => Promise.race([operation, cancelled]);
    const ensureCurrent = () => { if (epoch !== connectionEpoch.current) throw new Error("连接已取消。"); };
    try {
      endingRef.current = false;
      setErrorMessage(null); setActivity("正在连接，请稍候…");
      browserPlaybackCancelledRef.current = false;
      const context = audioContextRef.current ?? new AudioContext();
      audioContextRef.current = context;
      // Both calls happen during this click, before any awaited network work.
      const audioReady = context.resume();
      const avatar = avatarRef.current;
      avatar?.disconnect();
      const soundReady = playbackMode === "avatar_webrtc"
        ? (avatar ? avatar.unlockSound(context) : Promise.reject(new Error("播放器尚未准备好。")))
        : Promise.resolve();
      await waitFor(Promise.all([audioReady, soundReady])); ensureCurrent();
      if (context.state !== "running") throw new Error("请允许浏览器播放声音后重新连接。");
      if (playbackMode === "avatar_webrtc") {
        await waitFor(avatar!.connect()); ensureCurrent();
      }
      await waitFor(connect()); ensureCurrent();
      const binding = playbackMode === "avatar_webrtc" ? avatar?.binding() : null;
      if (playbackMode === "avatar_webrtc" && (!binding || !avatar?.readyForSpeech())) throw new Error("数字人尚未准备好，请重新连接。");
      socketRef.current!.sendStart({ playback_mode: playbackMode, avatar_binding: binding });
      setActiveConversation(true);
      setStopping(false);
      setErrorMessage(null);
      setActivity("已连接，正在准备聆听");
    } catch (error) {
      if (epoch === connectionEpoch.current) {
        disconnect();
        setErrorMessage(error instanceof Error ? error.message : "无法开始对话。");
      }
    } finally {
      clearTimeout(preparationTimeout); cancelPreparation.current = null;
      connectingRef.current = false; setConnecting(false);
    }
  }

  function stopConversation(): void {
    if (connectingRef.current) { disconnect(); return; }
    if (endingRef.current) return;
    endingRef.current = true;
    try {
      if (playbackModeRef.current === "avatar_webrtc") avatarRef.current?.disconnect();
      browserPlaybackCancelledRef.current = true;
      stopLipSync();
      resetExpressionLifecycle();
      const pending = pendingBrowserAudioRef.current;
      const active = activeBrowserAudioRef.current;
      pendingBrowserAudioRef.current = null;
      activeBrowserAudioRef.current = null;
      if (activeSourceRef.current) {
        activeSourceRef.current.stop();
        activeSourceRef.current = null;
      }
      const cancelled = active ?? pending;
      if (cancelled) socketRef.current?.sendBrowserPlaybackCancelled(cancelled.turnId, cancelled.audioId);
      socketRef.current?.sendStop();
      setStopping(true);
      setActivity("正在结束本次对话…");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "无法结束对话。");
    }
  }

  const canStart = !connecting && !activeConversation && !stopping;
  const canStop = connecting || (connection === "connected" && activeConversation && !stopping);

  function avatarFeedback(kind: AvatarFeedback, turn: AvatarTurn): void {
    if (turn.ws_session_id.startsWith("preview-")) {
      setVoiceState(kind === "started" ? "SPEAKING" : "IDLE");
      setActivity(kind === "estimated_finished" ? "短句播放流程估计结束" : kind === "started" ? "数字人音轨正在进入播放器" : "短句播放已停止");
      return;
    }
    if (playbackModeRef.current !== "avatar_webrtc" || turn.ws_session_id !== wsSessionRef.current) return;
    try { socketRef.current?.sendAvatarFeedback(kind, turn); }
    catch { setErrorMessage("对话连接已断开，数字人播放状态未送达。"); }
  }

  function changePlaybackMode(mode: string): void {
    browserPlaybackCancelledRef.current = true;
    activeSourceRef.current?.stop(); activeSourceRef.current = null;
    pendingBrowserAudioRef.current = null; activeBrowserAudioRef.current = null;
    avatarRef.current?.disconnect();
    playbackModeRef.current = mode; setPlaybackMode(mode);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Local Voice-Interactive AI System</p>
          <h1>本地语音交互AI系统</h1>
        </div>
        <span className={`connection ${connection}`}>连接状态：{connection === "connected" ? "已连接" : connection === "connecting" ? "正在连接" : connection === "error" ? "连接错误" : "未连接"}</span>
      </header>

      <section id="avatar-stage" className="stage" aria-label="数字人展示区域">
        <AvatarVideo ref={avatarRef} enabled={playbackMode === 'avatar_webrtc'} onDisconnected={() => { if (activeConversation && !endingRef.current) { endingRef.current = true; try { socketRef.current?.sendStop(); setStopping(true); } catch { setActiveConversation(false); } } }} onFeedback={avatarFeedback} />
      </section>

      <section className="console" aria-live="polite">
        <div className="console-header">
          <div>
            <span className="state-label">她的状态</span>
            <strong className="state-value">{STATE_LABELS[voiceState]}</strong>
          </div>
          <span className="activity">{activity}</span>
        </div>

        <div className="subtitle-grid">
          <article className="subtitle"><span className="speaker">你</span><p>{currentUser || "等待你的声音…"}</p></article>
          <article className="subtitle assistant"><span className="speaker">她</span><p>{currentAssistant || "我在这里。"}</p></article>
        </div>

        <div className="controls">
          <div className="button-group">
            <button className="primary" type="button" onClick={() => { void startConversation(); }} disabled={!canStart}>{connecting ? "正在连接…" : activeConversation ? "对话中" : "连接并开始对话"}</button>
            <button className="danger" type="button" onClick={stopConversation} disabled={!canStop}>结束对话</button>
          </div>
          <details className="advanced-settings"><summary>高级设置</summary>
            <label>备用播放方式
              <select value={playbackMode} onChange={(event) => changePlaybackMode(event.target.value)} disabled={activeConversation || connecting}>
                <option value="avatar_webrtc">数字人音轨</option><option value="browser">浏览器WAV回退</option>
              </select>
            </label>
            <p>默认使用数字人声音。切换播放方式前请先结束对话。</p>
          </details>
        </div>
        {SHOW_DEV_EXPRESSION_TESTS ? (
          <section aria-label="Development-only Live2D expression smoke test">
            <p>DEV ONLY: Live2D expression smoke test</p>
            <div className="button-group">
              <button type="button" onClick={() => { void runDevExpressionTest("neutral"); }}>neutral</button>
              {EXPRESSION_NAMES.map((name) => (
                <button key={name} type="button" onClick={() => { void runDevExpressionTest(name); }}>{name}</button>
              ))}
            </div>
            {expressionTestStatus ? <p className="activity">{expressionTestStatus}</p> : null}
            {selectedExpressionName ? (
              <div>
                <p>Selected: {selectedExpressionName}</p>
                <div className="button-group">
                  <button type="button" onClick={readSelectedExpressionParameter}>READ PARAM</button>
                  <button type="button" onClick={() => { void runDirectParameterTest(); }}>DIRECT PARAM TEST</button>
                  <button type="button" onClick={runDirectResetTest}>RESET DIRECT TEST</button>
                  <button type="button" onClick={() => { void runNamedExpressionDiagnostic(); }}>NAMED API DIAGNOSTIC</button>
                </div>
                {expressionParameterSnapshot ? <p>index={expressionParameterSnapshot.index}; range={expressionParameterSnapshot.minimum}..{expressionParameterSnapshot.maximum}; default={expressionParameterSnapshot.defaultValue}; current={expressionParameterSnapshot.value}</p> : null}
              </div>
            ) : null}
            {expressionDiagnostic ? (
              <div>
                <p>expression API: {expressionDiagnostic.expressionApiStatus}</p>
                <p>before={expressionDiagnostic.before.value}; after 1 frame={expressionDiagnostic.afterFirstFrame.value}; after 5 frames={expressionDiagnostic.afterSeveralFrames.value}</p>
              </div>
            ) : null}
            {directParameterDiagnostic ? (
              <p>direct {directParameterDiagnostic.name}: requested={directParameterDiagnostic.requestedValue}; before={directParameterDiagnostic.before.value}; after reset={directParameterDiagnostic.afterReset.value}; after immediate={directParameterDiagnostic.afterImmediate.value}; after 1 frame={directParameterDiagnostic.afterFirstFrame.value}; after 5 frames={directParameterDiagnostic.afterSeveralFrames.value}</p>
            ) : null}
            {expressionParameterStates ? <p>Expression params: {EXPRESSION_NAMES.map((name) => `${name}=${expressionParameterStates[name].value}`).join("; ")}</p> : null}
          </section>
        ) : null}
        {errorMessage ? <p className="error-message">{errorMessage}</p> : null}

        <section className="history">
          <h2>本次对话</h2>
          <div className="history-list">
            {history.length === 0 ? <p className="activity">连接后，字幕会在这里保留本次会话内容。</p> : history.map((entry, index) => (
              <article className="history-item" key={`${entry.turnId}-${entry.role}-${index}`}><span>{entry.role === "user" ? "你" : "她"}</span><p>{entry.text}</p></article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
