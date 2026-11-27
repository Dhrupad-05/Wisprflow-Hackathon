/**
 * Energy-based voice activity detection for the capture path.
 *
 * A pause is only ever allowed to finish a capture; the dialog layer decides
 * whether that becomes a read-back (silence) or a parsed answer (speech).
 * Thresholds follow the same field-type shape as the endpointing engine.
 *
 * Phase 2 polish:
 * - an adaptive noise floor keeps a fan or traffic from counting as speech;
 * - `minSpeechMs` stops one cough or door slam from starting/ending a turn;
 * - `feed(level, at)` accepts an explicit clock so behaviour is testable.
 */

export const VAD_DEFAULTS = Object.freeze({
  threshold: 0.018,
  startBlocks: 2,
  minSpeechMs: 0,
  noiseMultiplier: 2.5,
  maxNoiseFloor: 0.02,
  maxThreshold: 0.06,
  hardMaxMs: 30000,
  silenceMs: Object.freeze({
    short: 800,
    amount: 1100,
    name: 1100,
    digits: 1300
  })
});

export class VoiceActivityDetector {
  constructor({
    threshold = VAD_DEFAULTS.threshold,
    startBlocks = VAD_DEFAULTS.startBlocks,
    minSpeechMs = VAD_DEFAULTS.minSpeechMs,
    noiseMultiplier = VAD_DEFAULTS.noiseMultiplier,
    maxNoiseFloor = VAD_DEFAULTS.maxNoiseFloor,
    maxThreshold = VAD_DEFAULTS.maxThreshold,
    adaptive = true,
    silenceMs = VAD_DEFAULTS.silenceMs.short,
    slow = false,
    clock = () => Date.now()
  } = {}) {
    this.threshold = threshold;
    this.startBlocks = startBlocks;
    this.minSpeechMs = minSpeechMs;
    this.noiseMultiplier = noiseMultiplier;
    this.maxNoiseFloor = maxNoiseFloor;
    this.maxThreshold = maxThreshold;
    this.adaptive = adaptive;
    this.wait = Math.round(silenceMs * (slow ? 1.5 : 1));
    this.clock = clock;
    // Start where the dynamic threshold equals the configured threshold.
    this.noiseFloor = Math.min(threshold, maxNoiseFloor) / Math.max(1, noiseMultiplier);
    this.reset();
  }

  reset() {
    this.voicedBlocks = 0;
    this.spoke = false;
    this.ended = false;
    this.peak = 0;
    this.lastVoiceAt = 0;
    this.speechStartAt = 0;
    this.voiced = false;
  }

  /** Threshold in force right now, after the learned noise floor. */
  dynamicThreshold() {
    return Math.min(
      this.maxThreshold,
      Math.max(this.threshold, this.noiseFloor * this.noiseMultiplier)
    );
  }

  /** Learn the room level only while it is quiet, and never past the cap. */
  learn(level) {
    if (!this.adaptive || !Number.isFinite(level) || level >= this.dynamicThreshold()) return;
    this.noiseFloor = Math.min(
      this.maxNoiseFloor,
      this.noiseFloor * 0.98 + level * 0.02
    );
  }

  feed(level, at) {
    const now = at === undefined ? this.clock() : at;
    this.learn(level);
    const threshold = this.dynamicThreshold();
    const voiced = Number.isFinite(level) && level >= threshold;
    this.voiced = voiced;
    if (voiced) {
      if (this.voicedBlocks === 0) this.speechStartAt = now;
      this.voicedBlocks += 1;
      this.lastVoiceAt = now;
      this.peak = Math.max(this.peak, level);
    } else {
      this.voicedBlocks = 0;
    }
    const longEnough =
      this.minSpeechMs === 0 || now - this.speechStartAt >= this.minSpeechMs;
    const started =
      !this.spoke && this.voicedBlocks >= this.startBlocks && longEnough;
    if (started) this.spoke = true;
    const ended =
      this.spoke && !this.ended && now - this.lastVoiceAt >= this.wait;
    if (ended) this.ended = true;
    return {
      voiced,
      started,
      ended,
      spoke: this.spoke,
      peak: this.peak,
      speechMs: voiced || this.spoke ? now - this.speechStartAt : 0,
      threshold
    };
  }
}
