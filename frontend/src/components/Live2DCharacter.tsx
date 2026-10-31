"use client";

import { useEffect, useState } from "react";
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

const CORE_URL = "/live2d/runtime/live2dcubismcore.min.js";
const MODEL_URL = "/live2d/xiaojinli/04%E7%B4%AB%E7%9B%90.model3.json";
const MOUTH_PARAMETER_ID = "ParamMouthOpenY";

type MouthCoreModel = {
  getParameterIndex(parameterId: unknown): number;
  getParameterValueByIndex(parameterIndex: number): number;
  getParameterMinimumValue(parameterIndex: number): number;
  getParameterMaximumValue(parameterIndex: number): number;
  getParameterDefaultValue(parameterIndex: number): number;
  setParameterValueById(parameterId: unknown, value: number, weight?: number): void;
};

type CubismFrameworkRuntime = {
  CubismFramework: {
    getIdManager(): { getId(id: string): unknown };
  };
};

let pluginRegistered = false;

function cubismCoreIsAvailable(): boolean {
  return typeof (window as Window & { Live2DCubismCore?: unknown }).Live2DCubismCore !== "undefined";
}

function loadCubismCore(): Promise<void> {
  if (cubismCoreIsAvailable()) return Promise.resolve();

  const existing = document.querySelector<HTMLScriptElement>('script[data-live2d-cubism-core="true"]');
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Cubism Core could not be loaded.")), { once: true });
    });
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = CORE_URL;
    script.async = true;
    script.dataset.live2dCubismCore = "true";
    script.addEventListener("load", () => {
      if (!cubismCoreIsAvailable()) {
        reject(new Error("Cubism Core did not expose its browser runtime."));
        return;
      }
      resolve();
    }, { once: true });
    script.addEventListener("error", () => reject(new Error("Cubism Core is missing. Add the official runtime first.")), { once: true });
    document.head.appendChild(script);
  });
}

function displayErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.includes("Cubism Core")) return "Live2D runtime is waiting for the official Cubism Core.";
  return "Live2D load error";
}

export function Live2DCharacter() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let resizeObserver: ResizeObserver | undefined;
    let app: import("pixi.js").Application | undefined;
    let model: import("untitled-pixi-live2d-engine/cubism").Live2DModel | undefined;
    let removeMouthTicker: (() => void) | undefined;
    let resetMouthParameter: (() => void) | undefined;
    let unregisterExpressionHandler: (() => void) | undefined;

    async function initialise(): Promise<void> {
      const stage = document.getElementById("live2d-stage");
      if (!stage) throw new Error("Live2D stage is unavailable.");

      await loadCubismCore();
      if (disposed) return;

      const pixi = await import("pixi.js");
      const cubism = await import("untitled-pixi-live2d-engine/cubism");
      if (disposed) return;

      if (!pluginRegistered) {
        pixi.extensions.add(cubism.Live2DPlugin);
        pluginRegistered = true;
      }

      app = new pixi.Application();
      await app.init({
        width: Math.max(stage.clientWidth, 1),
        height: Math.max(stage.clientHeight, 1),
        autoDensity: true,
        backgroundAlpha: 0,
        preference: "webgl",
        resolution: Math.min(window.devicePixelRatio || 1, 2),
      });
      if (disposed) return;

      app.canvas.className = "live2d-canvas";
      app.canvas.setAttribute("aria-hidden", "true");
      stage.appendChild(app.canvas);

      model = await cubism.Live2DModel.from(MODEL_URL);
      if (disposed) return;
      model.anchor.set(0.5);
      app.stage.addChild(model);

      const framework = (cubism as unknown as CubismFrameworkRuntime).CubismFramework;
      const mouthParameter = framework.getIdManager().getId(MOUTH_PARAMETER_ID);
      const coreModel = model.internalModel.coreModel as unknown as MouthCoreModel;
      if (coreModel.getParameterIndex(mouthParameter) < 0) {
        throw new Error(`${MOUTH_PARAMETER_ID} is missing from the loaded Live2D model.`);
      }
      const mouthTicker = (): void => {
        coreModel.setParameterValueById(mouthParameter, mouthController.value);
      };
      resetMouthParameter = () => coreModel.setParameterValueById(mouthParameter, 0);
      const ticker = model.automator.ticker ?? app.ticker;
      ticker.add(mouthTicker, undefined, pixi.UPDATE_PRIORITY.LOW);
      removeMouthTicker = () => ticker.remove(mouthTicker);
      mouthController.reset();
      mouthTicker();

      const getExpressionParameter = (name: ExpressionName): { id: unknown; index: number } => {
        const id = framework.getIdManager().getId(name);
        const index = coreModel.getParameterIndex(id);
        if (index < 0) throw new Error(`Expression parameter ${name} is missing from the loaded Live2D model.`);
        return { id, index };
      };
      const readExpressionParameter = (name: ExpressionName): ExpressionParameterSnapshot => {
        const { index } = getExpressionParameter(name);
        return {
          index,
          value: coreModel.getParameterValueByIndex(index),
          minimum: coreModel.getParameterMinimumValue(index),
          maximum: coreModel.getParameterMaximumValue(index),
          defaultValue: coreModel.getParameterDefaultValue(index),
        };
      };
      const readAllExpressionParameters = (): ExpressionParameterStates => {
        const states = {} as ExpressionParameterStates;
        for (const name of EXPRESSION_NAMES) states[name] = readExpressionParameter(name);
        return states;
      };
      const resetAllExpressionParameters = (): ExpressionParameterStates => {
        for (const name of EXPRESSION_NAMES) {
          const { id, index } = getExpressionParameter(name);
          coreModel.setParameterValueById(id, coreModel.getParameterDefaultValue(index));
        }
        return readAllExpressionParameters();
      };
      const waitForFrames = async (count: number): Promise<void> => {
        for (let frame = 0; frame < count; frame += 1) {
          await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
        }
      };
      const observeExpressionApi = async (name: ExpressionName): Promise<ExpressionRuntimeDiagnostic["expressionApiStatus"]> => {
        const expressionPromise = model?.expression(name) ?? Promise.resolve(false);
        const timeoutPromise = new Promise<"timed_out">((resolve) => {
          window.setTimeout(() => resolve("timed_out"), 5000);
        });
        try {
          const result = await Promise.race([expressionPromise, timeoutPromise]);
          if (result === "timed_out") return "timed_out";
          return result ? "resolved_true" : "resolved_false";
        } catch {
          return "rejected";
        }
      };
      unregisterExpressionHandler = expressionController.register({
        async apply(name: ExpressionName): Promise<boolean> {
          try {
            resetAllExpressionParameters();
            const { id } = getExpressionParameter(name);
            coreModel.setParameterValueById(id, 1);
            return true;
          } catch {
            try {
              resetAllExpressionParameters();
            } catch {
              // Expression failures must not affect the audio path.
            }
            return false;
          }
        },
        reset(): void {
          try {
            resetAllExpressionParameters();
          } catch {
            // Cleanup remains best-effort if a model has already been disposed.
          }
        },
        readParameter(name: ExpressionName): ExpressionParameterSnapshot | null {
          try {
            return readExpressionParameter(name);
          } catch {
            return null;
          }
        },
        readAllParameters(): ExpressionParameterStates | null {
          try {
            return readAllExpressionParameters();
          } catch {
            return null;
          }
        },
        resetAllParameters(): ExpressionParameterStates | null {
          try {
            return resetAllExpressionParameters();
          } catch {
            return null;
          }
        },
        async diagnose(name: ExpressionName): Promise<ExpressionRuntimeDiagnostic | null> {
          try {
            const before = readExpressionParameter(name);
            const expressionApiStatus = await observeExpressionApi(name);
            await waitForFrames(1);
            const afterFirstFrame = readExpressionParameter(name);
            await waitForFrames(4);
            const afterSeveralFrames = readExpressionParameter(name);
            return { name, before, expressionApiStatus, afterFirstFrame, afterSeveralFrames };
          } catch {
            return null;
          }
        },
        async setDirect(name: ExpressionName, value: number): Promise<DirectParameterDiagnostic | null> {
          try {
            const { id } = getExpressionParameter(name);
            const before = readExpressionParameter(name);
            resetAllExpressionParameters();
            const afterReset = readExpressionParameter(name);
            coreModel.setParameterValueById(id, value);
            const afterImmediate = readExpressionParameter(name);
            await waitForFrames(1);
            const afterFirstFrame = readExpressionParameter(name);
            await waitForFrames(4);
            const afterSeveralFrames = readExpressionParameter(name);
            return { name, requestedValue: value, before, afterReset, afterImmediate, afterFirstFrame, afterSeveralFrames };
          } catch {
            return null;
          }
        },
      });

      const baseWidth = Math.max(model.width, 1);
      const baseHeight = Math.max(model.height, 1);

      const fitModel = (): void => {
        if (!app || !model) return;
        const width = Math.max(stage.clientWidth, 1);
        const height = Math.max(stage.clientHeight, 1);
        const hudSafeArea = Math.min(280, height * 0.32);
        const usableHeight = Math.max(height - hudSafeArea, 1);
        app.renderer.resize(width, height);

        const scale = Math.min((width * 0.72) / baseWidth, (usableHeight * 0.94) / baseHeight);
        model.scale.set(scale);
        model.position.set(width / 2, usableHeight / 2);
      };

      fitModel();
      resizeObserver = new ResizeObserver(fitModel);
      resizeObserver.observe(stage);
      stage.querySelector<HTMLElement>(".placeholder")?.setAttribute("hidden", "true");
    }

    initialise().catch((caughtError: unknown) => {
      if (!disposed) setError(displayErrorMessage(caughtError));
    });

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      mouthController.reset();
      expressionController.reset();
      unregisterExpressionHandler?.();
      resetMouthParameter?.();
      removeMouthTicker?.();
      if (model && app) app.stage.removeChild(model);
      model?.destroy({ children: true, texture: true, baseTexture: true });
      app?.destroy({ removeView: true }, true);
    };
  }, []);

  return error ? <p className="live2d-error" role="status">{error}</p> : null;
}
