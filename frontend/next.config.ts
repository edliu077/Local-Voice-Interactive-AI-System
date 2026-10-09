import type { NextConfig } from "next";

function localPort(name: string, fallback: number): number {
  const value = Number(process.env[name] ?? fallback);
  if (!Number.isInteger(value) || value < 1 || value > 65535) {
    throw new Error(`${name} must be an integer between 1 and 65535`);
  }
  return value;
}

const wsPort = localPort("LVIAI_WS_PORT", 8767);

const nextConfig: NextConfig = {
  env: {
    LVIAI_WS_URL: `ws://127.0.0.1:${wsPort}`,
    NEXT_PUBLIC_LVIAI_LIVE2D_CORE_URL:
      process.env.NEXT_PUBLIC_LVIAI_LIVE2D_CORE_URL ?? "/live2d/runtime/live2dcubismcore.min.js",
    NEXT_PUBLIC_LVIAI_LIVE2D_MODEL_URL:
      process.env.NEXT_PUBLIC_LVIAI_LIVE2D_MODEL_URL ?? "/live2d/model/model3.json",
  },
};

export default nextConfig;
