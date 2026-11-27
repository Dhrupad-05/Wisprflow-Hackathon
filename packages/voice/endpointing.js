export const DEFAULT_THRESHOLDS = Object.freeze({ short: 1200, amount: 2500, name: 2500, digits: 3000 });
export const END_WORDS = Object.freeze({
  en: ["done", "that's all", "stop"],
  hi: ["bas", "ho gaya", "बस", "हो गया"],
  bn: ["bas", "হয়ে গেছে", "হয়ে গেছে", "বাস"]
});
export const CONNECTORS = Object.freeze(["aur", "and", "ebong", "और", "এবং"]);

export class EndpointingEngine {
  constructor({ clock = () => Date.now(), setTimer = setTimeout, clearTimer = clearTimeout, threshold = DEFAULT_THRESHOLDS, slow = false, onEnd = () => {}, onReask = () => {} } = {}) {
    this.clock = clock;
    this.setTimer = setTimer;
    this.clearTimer = clearTimer;
    this.threshold = threshold;
    this.slow = slow;
    this.onEnd = onEnd;
    this.onReask = onReask;
    this.timer = null;
    this.started = 0;
    this.fieldType = "short";
    this.language = "en";
    this.text = "";
    this.confidence = 1;
  }

  begin({ fieldType = "short", language = "en" } = {}) {
    this.cancel();
    this.fieldType = fieldType;
    this.language = language;
    this.started = this.clock();
  }

  update(text, confidence = 1) {
    this.text = String(text || "").trim();
    this.confidence = confidence;
    if (!this.text || confidence < 0.35) return this.onReask({ reason: "short_or_low_confidence", text: this.text });
    if (this.hasEndWord(this.text)) return this.finish("end_word");
    this.schedule();
  }

  schedule() {
    if (!this.started) return;
    const multiplier = this.slow ? 1.5 : 1;
    let wait = (this.threshold[this.fieldType] || this.threshold.short) * multiplier;
    const lower = this.text.toLowerCase();
    if (CONNECTORS.some((connector) => lower.endsWith(connector))) wait *= 1.5;
    this.clearTimer(this.timer);
    this.timer = this.setTimer(() => this.finish("pause"), wait);
  }

  hasEndWord(text) {
    const words = END_WORDS[this.language] || END_WORDS.en;
    const lower = text.toLowerCase().trim();
    return words.some((word) => lower === word || lower.endsWith(` ${word}`));
  }

  finish(reason = "pause") {
    this.clearTimer(this.timer);
    this.timer = null;
    if (!this.text || this.confidence < 0.35) return this.onReask({ reason: "short_or_low_confidence", text: this.text });
    const result = { text: this.text, reason, elapsed: this.clock() - this.started };
    this.started = 0;
    return this.onEnd(result);
  }

  cancel() {
    this.clearTimer(this.timer);
    this.timer = null;
    this.started = 0;
    this.text = "";
  }
}
