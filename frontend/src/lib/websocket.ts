import type { ConnectionState, WsEvent } from "./types";
import { isWsEvent } from "./types";

export const I0_WEBSOCKET_URL = process.env.LVIAI_WS_URL ?? "ws://127.0.0.1:8767";

export interface VoiceSocketCallbacks {
  onConnectionState: (state: ConnectionState) => void;
  onEvent: (event: WsEvent) => void;
  onAudioBinary: (audio: ArrayBuffer) => void;
  onError: (message: string) => void;
}

export class VoiceSocket {
  private socket: WebSocket | null = null;
  private manualClose = false;

  connect(callbacks: VoiceSocketCallbacks): void {
    if (this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) return;
    this.manualClose = false;
    callbacks.onConnectionState("connecting");
    const socket = new WebSocket(I0_WEBSOCKET_URL);
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    socket.onopen = () => callbacks.onConnectionState("connected");
    socket.onmessage = (message) => {
      if (message.data instanceof ArrayBuffer) {
        callbacks.onAudioBinary(message.data);
        return;
      }
      if (typeof message.data !== "string") {
        callbacks.onError("收到不支持的 WebSocket 消息类型。");
        return;
      }
      try {
        const parsed: unknown = JSON.parse(message.data);
        if (!isWsEvent(parsed)) throw new Error("收到格式无效的 WebSocket 事件。");
        callbacks.onEvent(parsed);
      } catch (error) {
        callbacks.onError(error instanceof Error ? error.message : "无法读取 WebSocket 事件。");
      }
    };
    socket.onerror = () => callbacks.onError("无法连接本机语音服务。");
    socket.onclose = () => {
      this.socket = null;
      callbacks.onConnectionState(this.manualClose ? "disconnected" : "error");
    };
  }

  sendStart(maxTurns: number): void { this.send({ type: "start", max_turns: maxTurns }); }
  sendStop(): void { this.send({ type: "stop" }); }
  sendBrowserPlaybackStarted(turnId: number, audioId: string): void {
    this.send({ type: "browser_playback_started", turn_id: turnId, audio_id: audioId });
  }
  sendBrowserPlaybackFinished(turnId: number, audioId: string): void {
    this.send({ type: "browser_playback_finished", turn_id: turnId, audio_id: audioId });
  }
  sendBrowserPlaybackCancelled(turnId: number, audioId: string): void {
    this.send({ type: "browser_playback_cancelled", turn_id: turnId, audio_id: audioId });
  }
  sendAudioPlaybackError(turnId: number, audioId: string, code: string): void {
    this.send({ type: "audio_playback_error", turn_id: turnId, audio_id: audioId, code });
  }

  disconnect(): void {
    this.manualClose = true;
    this.socket?.close();
    this.socket = null;
  }

  private send(message: Record<string, unknown>): void {
    if (this.socket?.readyState !== WebSocket.OPEN) throw new Error("WebSocket is not connected");
    this.socket.send(JSON.stringify(message));
  }
}
