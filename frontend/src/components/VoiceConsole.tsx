"use client";

import { useEffect, useRef, useState } from "react";
import { Live2DCharacter } from "@/components/Live2DCharacter";
import { mouthController } from "@/lib/mouth-controller";
import { VoiceSocket } from "@/lib/websocket";
import type { ConnectionState, ConversationEntry, VoiceState, WsEvent } from "@/lib/types";

const STATE_LABELS: Record<VoiceState, string> = {
  IDLE: "待机",
  LISTENING: "正在听你说话…",
  TRANSCRIBING: "正在识别…",
  THINKING: "正在思考…",
  SYNTHESIZING: "正在准备声音…",
  SPEAKING: "正在说话…",
  ERROR: "发生错误",
};

type PendingBrowserAudio = {
  audioId: string;
  turnId: number;
  byteLength: number;
};

function textValue(data: Record<string, unknown>, key: string): string | null {
  const value = data[key];
  return typeof value === "string" ? value : null;
}

function stateValue(data: Record<string, unknown>): VoiceState | null {
  const value = textValue(data, "state");
  return value && value in STATE_LABELS ? value as VoiceState : null;
}

export function VoiceConsole() {
  const socketRef = useRef<VoiceSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const activeSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const pendingBrowserAudioRef = useRef<PendingBrowserAudio | null>(null);
  const activeBrowserAudioRef = useRef<PendingBrowserAudio | null>(null);
  const browserPlaybackCancelledRef = useRef(false);
  const playbackModeRef = useRef("winsound");
  const lipSyncFrameRef = useRef<number | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("disconnected");
  const [backendReady, setBackendReady] = useState(false);
  const [playbackMode, setPlaybackMode] = useState("winsound");
  const [activeConversation, setActiveConversation] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>("IDLE");
  const [currentUser, setCurrentUser] = useState("");
  const [currentAssistant, setCurrentAssistant] = useState("");
  const [history, setHistory] = useState<ConversationEntry[]>([]);
  const [maxTurns, setMaxTurns] = useState(6);
  const [activity, setActivity] = useState("等待连接本机语音服务");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => () => {
    browserPlaybackCancelledRef.current = true;
    stopLipSync();
    activeSourceRef.current?.stop();
    socketRef.current?.disconnect();
  }, []);

  function appendHistory(entry: ConversationEntry): void {
    setHistory((previous) => [...previous, entry].slice(-12));
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
    const pending = pendingBrowserAudioRef.current;
    pendingBrowserAudioRef.current = null;
    if (!pending) {
      stopLipSync();
      setErrorMessage("收到未配对的音频数据。");
      return;
    }
    if (audio.byteLength !== pending.byteLength) {
      stopLipSync();
      sendBrowserPlaybackError(pending, "binary_size_mismatch");
      setErrorMessage("音频数据大小校验失败。");
      return;
    }
    const context = audioContextRef.current;
    if (!context || context.state !== "running") {
      stopLipSync();
      sendBrowserPlaybackError(pending, "audio_context_suspended");
      setErrorMessage("浏览器音频上下文未准备好。");
      return;
    }
    try {
      const decoded = await context.decodeAudioData(audio);
      if (browserPlaybackCancelledRef.current) {
        stopLipSync();
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
      setActivity("AI 正在通过浏览器扬声器说话");
    } catch {
      stopLipSync();
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
        setBackendReady(true);
        playbackModeRef.current = textValue(data, "playback_mode") ?? "winsound";
        setPlaybackMode(playbackModeRef.current);
        setErrorMessage(null);
        setActivity("本机语音服务已准备好");
        break;
      case "state": {
        const nextState = stateValue(data);
        if (nextState) {
          setVoiceState(nextState);
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
          setCurrentAssistant(text);
          appendHistory({ role: "assistant", text, turnId: event.turn_id });
        }
        break;
      }
      case "audio_ready": {
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
      case "playback_started":
        setActivity(playbackModeRef.current === "browser" ? "AI 正在通过浏览器扬声器说话" : "AI 正在通过本机扬声器说话");
        break;
      case "playback_finished":
        setActivity("播放完成");
        break;
      case "turn_complete":
        setActivity(`第 ${event.turn_id} 轮已完成`);
        break;
      case "error":
        setErrorMessage(textValue(data, "message") ?? "本机语音服务发生错误。");
        setVoiceState("ERROR");
        break;
      case "session_stopped":
        setActiveConversation(false);
        setStopping(false);
        setVoiceState("IDLE");
        setActivity("本次对话已结束");
        break;
      default:
        break;
    }
  }

  function connect(): void {
    if (!socketRef.current) socketRef.current = new VoiceSocket();
    setErrorMessage(null);
    socketRef.current.connect({
      onConnectionState: (nextConnection) => {
        setConnection(nextConnection);
        if (nextConnection !== "connected") {
          stopLipSync();
          setBackendReady(false);
        }
      },
      onEvent: handleEvent,
      onAudioBinary: (audio) => { void handleAudioBinary(audio); },
      onError: (message) => {
        setErrorMessage(message);
        setConnection("error");
      },
    });
  }

  function disconnect(): void {
    stopLipSync();
    socketRef.current?.disconnect();
    setConnection("disconnected");
    setBackendReady(false);
    setActiveConversation(false);
    setStopping(false);
    setVoiceState("IDLE");
    setActivity("已断开连接");
  }

  async function startConversation(): Promise<void> {
    try {
      browserPlaybackCancelledRef.current = false;
      if (playbackMode === "browser") {
        const context = audioContextRef.current ?? new AudioContext();
        audioContextRef.current = context;
        await context.resume();
        if (context.state !== "running") throw new Error("AudioContext is not running");
      }
      socketRef.current?.sendStart(maxTurns);
      setActiveConversation(true);
      setStopping(false);
      setErrorMessage(null);
      setActivity("已请求开始对话，等待本机状态事件");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "无法开始对话。");
    }
  }

  function stopConversation(): void {
    try {
      browserPlaybackCancelledRef.current = true;
      stopLipSync();
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

  const canStart = connection === "connected" && backendReady && !activeConversation;
  const canStop = connection === "connected" && activeConversation && !stopping;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Local Voice-Interactive AI System</p>
          <h1>本地语音交互AI系统</h1>
        </div>
        <span className={`connection ${connection}`}>连接状态：{connection === "connected" ? "已连接" : connection === "connecting" ? "正在连接" : connection === "error" ? "连接错误" : "未连接"}</span>
      </header>

      <section id="live2d-stage" className="stage" aria-label="Live2D interaction stage">
        <div className="placeholder">Live2D Interaction</div>
        <Live2DCharacter />
      </section>

      <section className="console" aria-live="polite">
        <div className="console-header">
          <div>
            <span className="state-label">系统状态</span>
            <strong className="state-value">{STATE_LABELS[voiceState]}</strong>
          </div>
          <span className="activity">{activity}</span>
        </div>

        <div className="subtitle-grid">
          <article className="subtitle"><span className="speaker">你</span><p>{currentUser || "等待你的声音…"}</p></article>
          <article className="subtitle assistant"><span className="speaker">AI</span><p>{currentAssistant || "AI 助手已就绪。"}</p></article>
        </div>

        <div className="controls">
          <div className="button-group">
            {connection === "connected" || connection === "connecting" ? (
              <button type="button" onClick={disconnect}>断开连接</button>
            ) : (
              <button type="button" onClick={connect}>{connection === "error" ? "重新连接" : "连接"}</button>
            )}
            <button className="primary" type="button" onClick={startConversation} disabled={!canStart}>开始对话</button>
            <button className="danger" type="button" onClick={stopConversation} disabled={!canStop}>结束对话</button>
          </div>
          <label className="turn-select">轮数
            <select value={maxTurns} onChange={(event) => setMaxTurns(Number(event.target.value))} disabled={activeConversation}>
              <option value={1}>1</option><option value={2}>2</option><option value={6}>6</option>
            </select>
          </label>
        </div>
        {errorMessage ? <p className="error-message">{errorMessage}</p> : null}

        <section className="history">
          <h2>本次对话</h2>
          <div className="history-list">
            {history.length === 0 ? <p className="activity">连接后，字幕会在这里保留本次会话内容。</p> : history.map((entry, index) => (
              <article className="history-item" key={`${entry.turnId}-${entry.role}-${index}`}><span>{entry.role === "user" ? "你" : "AI"}</span><p>{entry.text}</p></article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
