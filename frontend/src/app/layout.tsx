import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "本地语音交互AI系统",
  description: "在熟悉的书房里，自然地聊一会儿。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
