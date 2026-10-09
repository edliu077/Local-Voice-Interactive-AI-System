/** Shared, render-loop-safe mouth scalar for browser-audio lip sync. */
class MouthController {
  private currentValue = 0;

  get value(): number {
    return this.currentValue;
  }

  set value(nextValue: number) {
    this.currentValue = Math.min(1, Math.max(0, Number.isFinite(nextValue) ? nextValue : 0));
  }

  reset(): void {
    this.currentValue = 0;
  }
}

export const mouthController = new MouthController();
