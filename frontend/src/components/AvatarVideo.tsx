"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { AvatarClient, type AvatarBinding, type AvatarFeedback, type AvatarTurn } from "@/lib/avatar-client";

export type AvatarVideoHandle = { unlockSound: (context: AudioContext) => Promise<void>; connect: () => Promise<void>; disconnect: () => void; binding: () => AvatarBinding | null; prepare: (turn: AvatarTurn) => void; readyForSpeech: () => boolean };
type Props = { enabled: boolean; onDisconnected: () => void; onFeedback: (kind: AvatarFeedback, turn: AvatarTurn) => void };

export const AvatarVideo = forwardRef<AvatarVideoHandle, Props>(function AvatarVideo(props, ref) {
  const video = useRef<HTMLVideoElement>(null);
  const client = useRef<AvatarClient | null>(null);
  const latest = useRef(props);
  const [status, setStatus] = useState("等待连接数字人");
  const [error, setError] = useState("");
  useEffect(() => { latest.current = props; }, [props]);
  useEffect(() => { if (!props.enabled) client.current?.disconnect(); }, [props.enabled]);
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const resize = () => element.parentElement?.style.setProperty('--avatar-native-width', `${1278 / Math.max(1, window.devicePixelRatio)}px`);
    resize(); window.addEventListener('resize', resize);
    const instance = new AvatarClient(element, {
      status: (message) => { setStatus(message); if (message === "数字人已断开") latest.current.onDisconnected(); },
      error: setError, stats: () => {},
      feedback: (kind, turn) => latest.current.onFeedback(kind, turn),
    });
    client.current = instance;
    return () => { window.removeEventListener('resize', resize); instance.disconnect(); client.current = null; };
  }, []);
  async function connect() {
    setError("");
    if (!client.current) throw new Error("播放器尚未准备好。");
    try { await client.current.connect(); await client.current.enableSound(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "连接失败。"); throw reason; }
  }
  useImperativeHandle(ref, () => ({ unlockSound: (context) => {
    if (!client.current) return Promise.reject(new Error("播放器尚未准备好。"));
    return client.current.unlockSound(context);
  }, connect, disconnect: () => client.current?.disconnect(), binding: () => client.current?.getBinding() ?? null, prepare: (turn) => client.current?.prepareTurn(turn), readyForSpeech: () => (client.current?.isReady() && client.current.hasSoundPermission() && client.current.isIdle()) ?? false }));
  return <div className="avatar-panel">
    <video ref={video} className="avatar-video" poster="/avatar-idle.png" width={1278} height={720} playsInline autoPlay aria-label="数字人实时画面" />
    <div className="avatar-controls">
      <span role="status">{status}</span>
    </div>
    {error ? <p className="avatar-error" role="alert">{error}</p> : null}
  </div>;
});
