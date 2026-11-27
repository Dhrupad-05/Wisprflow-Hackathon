/**
 * Barge-in gate for text-to-speech playback.
 *
 * The microphone stays open while the assistant speaks, but the first
 * `graceMs` of playback is ignored so the speaker's own onset cannot stop it.
 * After that the gate needs sustained voice (startBlocks + minSpeechMs) before
 * it reports an interruption, which keeps echo and clicks from cutting speech.
 */

import { VAD_DEFAULTS, VoiceActivityDetector } from "./vad.js";

export const BARGE_DEFAULTS = Object.freeze({
  graceMs: 400,
  threshold: 0.03,
  startBlocks: 3,
  minSpeechMs: 100
});

export class BargeInMonitor {
  constructor({
    graceMs = BARGE_DEFAULTS.graceMs,
    threshold = BARGE_DEFAULTS.threshold,
    startBlocks = BARGE_DEFAULTS.startBlocks,
    minSpeechMs = BARGE_DEFAULTS.minSpeechMs,
    slow = false,
    clock = () => Date.now()
  } = {}) {
    this.clock = clock;
    this.graceMs = graceMs;
    this.triggered = false;
    this.armed = false;
    this.armedAt = 0;
    this.vad = new VoiceActivityDetector({
      threshold,
      startBlocks,
      minSpeechMs,
      silenceMs: VAD_DEFAULTS.silenceMs.short,
      slow
    });
  }

  get listening() {
    return this.armed;
  }

  arm() {
    this.triggered = false;
    this.armed = true;
    this.armedAt = this.clock();
    this.vad.reset();
    return this.armedAt + this.graceMs;
  }

  disarm() {
    this.triggered = false;
    this.armed = false;
    this.armedAt = 0;
    this.vad.reset();
  }

  feed(level, at) {
    const now = at === undefined ? this.clock() : at;
    if (!this.armed) return { interrupt: false, gate: "disarmed" };
    if (now - this.armedAt < this.graceMs) return { interrupt: false, gate: "grace" };
    const activity = this.vad.feed(level, now);
    if (!this.triggered && activity.started) {
      this.triggered = true;
      return { interrupt: true, gate: "speech", activity };
    }
    return { interrupt: false, gate: "listening", activity };
  }
}
