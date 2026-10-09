import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "本地语音交互AI系统 | Local Voice-Interactive AI System",
  description: "A locally deployed real-time conversational AI system integrating speech recognition, local LLM inference, speech synthesis, browser audio, and Live2D avatar interaction.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
