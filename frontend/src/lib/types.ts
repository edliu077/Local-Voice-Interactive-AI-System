export type VoiceState =
  | "IDLE"
  | "LISTENING"
  | "TRANSCRIBING"
  | "THINKING"
  | "SYNTHESIZING"
  | "SPEAKING"
  | "ERROR";

export type ConnectionState = "disconnected" | "connecting" | "connected" | "error";

export interface BaseWsEvent<TData extends Record<string, unknown> = Record<string, unknown>> {
  type: string;
  timestamp: number;
  session_id: string;
  turn_id: number;
  data: TData;
}

export interface StateEvent extends BaseWsEvent<{ state: VoiceState }> { type: "state"; }
export interface UserTranscriptEvent extends BaseWsEvent<{ text: string }> { type: "user_transcript"; }
export interface AssistantTextEvent extends BaseWsEvent<{ text: string }> { type: "assistant_text"; }
export interface SessionReadyEvent extends BaseWsEvent<{ stt: string; llm: string; tts: string; vad: string; playback_mode: string }> { type: "session_ready"; }
export interface AudioReadyEvent extends BaseWsEvent<{
  audio_path?: string;
  transport?: "websocket_binary";
  audio_id?: string;
  byte_length?: number;
  content_type?: "audio/wav";
  duration_seconds?: number;
  sample_rate?: number;
}> { type: "audio_ready"; }
export interface ErrorEvent extends BaseWsEvent<{ message: string; recoverable: boolean }> { type: "error"; }
export interface SessionStoppedEvent extends BaseWsEvent<{ reason: string }> { type: "session_stopped"; }
export type WsEvent = BaseWsEvent | StateEvent | UserTranscriptEvent | AssistantTextEvent | SessionReadyEvent | AudioReadyEvent | ErrorEvent | SessionStoppedEvent;

export interface ConversationEntry { role: "user" | "assistant"; text: string; turnId: number; }

export function isWsEvent(value: unknown): value is WsEvent {
  if (typeof value !== "object" || value === null) return false;
  const event = value as Partial<BaseWsEvent>;
  return typeof event.type === "string" && typeof event.timestamp === "number" && typeof event.session_id === "string" && typeof event.turn_id === "number" && typeof event.data === "object" && event.data !== null;
}
