/** Imperative, event-level bridge for explicitly named Live2D expressions. */
export const EXPRESSION_NAMES = ["aixin", "fu", "kuku", "xingxing"] as const;

export type ExpressionName = (typeof EXPRESSION_NAMES)[number];

export type ExpressionParameterSnapshot = {
  index: number;
  value: number;
  minimum: number;
  maximum: number;
  defaultValue: number;
};

export type ExpressionParameterStates = Record<ExpressionName, ExpressionParameterSnapshot>;

export type ExpressionRuntimeDiagnostic = {
  name: ExpressionName;
  before: ExpressionParameterSnapshot;
  expressionApiStatus: "resolved_true" | "resolved_false" | "rejected" | "timed_out";
  afterFirstFrame: ExpressionParameterSnapshot;
  afterSeveralFrames: ExpressionParameterSnapshot;
};

export type DirectParameterDiagnostic = {
  name: ExpressionName;
  requestedValue: number;
  before: ExpressionParameterSnapshot;
  afterReset: ExpressionParameterSnapshot;
  afterImmediate: ExpressionParameterSnapshot;
  afterFirstFrame: ExpressionParameterSnapshot;
  afterSeveralFrames: ExpressionParameterSnapshot;
};

type ExpressionHandler = {
  apply(name: ExpressionName): Promise<boolean>;
  reset(): void;
  readParameter(name: ExpressionName): ExpressionParameterSnapshot | null;
  readAllParameters(): ExpressionParameterStates | null;
  resetAllParameters(): ExpressionParameterStates | null;
  diagnose(name: ExpressionName): Promise<ExpressionRuntimeDiagnostic | null>;
  setDirect(name: ExpressionName, value: number): Promise<DirectParameterDiagnostic | null>;
};

function isExpressionName(value: string): value is ExpressionName {
  return EXPRESSION_NAMES.some((name) => name === value);
}

class ExpressionController {
  private handler: ExpressionHandler | null = null;

  register(handler: ExpressionHandler): () => void {
    this.handler = handler;
    return () => {
      if (this.handler === handler) this.handler = null;
    };
  }

  async apply(name: string): Promise<boolean> {
    const handler = this.handler;
    if (!handler || !isExpressionName(name)) {
      handler?.reset();
      return false;
    }
    try {
      const applied = await handler.apply(name);
      if (!applied) handler.reset();
      return applied;
    } catch {
      handler.reset();
      return false;
    }
  }

  reset(): void {
    this.handler?.reset();
  }

  async diagnose(name: string): Promise<ExpressionRuntimeDiagnostic | null> {
    const handler = this.handler;
    if (!handler || !isExpressionName(name)) {
      handler?.reset();
      return null;
    }
    try {
      return await handler.diagnose(name);
    } catch {
      handler.reset();
      return null;
    }
  }

  async setDirect(name: string, value: number): Promise<DirectParameterDiagnostic | null> {
    const handler = this.handler;
    if (!handler || !isExpressionName(name)) {
      handler?.reset();
      return null;
    }
    try {
      return await handler.setDirect(name, value);
    } catch {
      handler.reset();
      return null;
    }
  }

  readParameter(name: string): ExpressionParameterSnapshot | null {
    const handler = this.handler;
    if (!handler || !isExpressionName(name)) return null;
    try {
      return handler.readParameter(name);
    } catch {
      return null;
    }
  }

  readAllParameters(): ExpressionParameterStates | null {
    try {
      return this.handler?.readAllParameters() ?? null;
    } catch {
      return null;
    }
  }

  resetAllParameters(): ExpressionParameterStates | null {
    try {
      return this.handler?.resetAllParameters() ?? null;
    } catch {
      return null;
    }
  }
}

export const expressionController = new ExpressionController();
