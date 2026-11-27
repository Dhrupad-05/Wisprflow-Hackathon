/**
 * Microphone capture helpers.
 *
 * Design rules (Phase 1):
 * - never race getUserMedia against a timer; wait for the permission prompt;
 * - resume the AudioContext from the click handler (Chrome starts suspended);
 * - prefer AudioWorklet, fall back to ScriptProcessor only if needed;
 * - expose live RMS so the UI can show a level meter and drive VAD;
 * - always stop tracks on failure so the mic indicator never stays on.
 */

const TARGET_RATE = 16000;

export function floatToPcm16(samples) {
  const output = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const value = Math.max(-1, Math.min(1, samples[index]));
    output[index] = value < 0 ? value * 0x8000 : value * 0x7fff;
  }
  return output;
}

export function pcm16ToWav(samples, sampleRate = TARGET_RATE) {
  const pcm = samples instanceof Int16Array ? samples : floatToPcm16(samples);
  const buffer = new ArrayBuffer(44 + pcm.byteLength);
  const view = new DataView(buffer);
  const write = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  write(0, "RIFF"); view.setUint32(4, 36 + pcm.byteLength, true); write(8, "WAVE"); write(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, pcm.byteLength, true);
  new Int16Array(buffer, 44).set(pcm);
  return new Blob([buffer], { type: "audio/wav" });
}

export function resampleTo16k(samples, sourceRate) {
  if (sourceRate === TARGET_RATE) return samples;
  const ratio = sourceRate / TARGET_RATE;
  const output = new Float32Array(Math.round(samples.length / ratio));
  for (let index = 0; index < output.length; index += 1) output[index] = samples[Math.min(samples.length - 1, Math.round(index * ratio))];
  return output;
}

export function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

export class MicrophoneError extends Error {
  constructor(code, detail = "") {
    super(detail || code);
    this.name = "MicrophoneError";
    this.code = code;
  }
}

export function normalizeMicrophoneError(error) {
  const name = error && error.name ? error.name : "Error";
  const map = {
    NotAllowedError: "permission-denied",
    SecurityError: "permission-denied",
    PermissionDeniedError: "permission-denied",
    NotFoundError: "no-device",
    DevicesNotFoundError: "no-device",
    NotReadableError: "device-busy",
    TrackStartError: "device-busy",
    OverconstrainedError: "device-unavailable",
    ConstraintNotSatisfiedError: "device-unavailable",
    AbortError: "microphone-error"
  };
  return new MicrophoneError(map[name] || "microphone-error", error && error.message);
}

let sharedContext = null;
let workletLoaded = false;

function audioContextClass() {
  return window.AudioContext || window.webkitAudioContext;
}

function currentContext() {
  const Ctx = audioContextClass();
  if (!Ctx) throw new MicrophoneError("unsupported-context");
  if (!sharedContext || sharedContext.state === "closed") sharedContext = new Ctx();
  return sharedContext;
}

async function loadWorklet(context) {
  if (workletLoaded) return;
  await context.audioWorklet.addModule("/audio-worklet.js");
  workletLoaded = true;
}

export function microphoneAvailable() {
  return Boolean(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia && audioContextClass());
}

export async function listMicrophones() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return [];
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices
      .filter((device) => device.kind === "audioinput")
      .map((device, index) => ({ id: device.deviceId, label: device.label || `Microphone ${index + 1}` }));
  } catch {
    return [];
  }
}

/**
 * Open the microphone and return a controller.
 * `stop()` resolves with a 16 kHz PCM16 WAV blob (or null when discarded).
 */
export async function captureMicrophone({ deviceId, onLevel = () => {}, onMaxStop = () => {}, maxMs = 30000 } = {}) {
  if (!window.isSecureContext) throw new MicrophoneError("insecure-context");
  if (!microphoneAvailable()) throw new MicrophoneError("unsupported-context");

  const context = currentContext();
  try {
    await context.resume();
  } catch {
    // Safari may already be running; capture still works.
  }

  const audioConstraints = {
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true
  };
  if (deviceId && deviceId !== "default") audioConstraints.deviceId = { exact: deviceId };

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
  } catch (error) {
    throw normalizeMicrophoneError(error);
  }

  const track = stream.getAudioTracks()[0];
  const source = context.createMediaStreamSource(stream);
  const mute = context.createGain();
  mute.gain.value = 0;
  mute.connect(context.destination);

  const chunks = [];
  let peak = 0;
  let stopped = false;
  const collect = (samples) => {
    chunks.push(new Float32Array(samples));
    let energy = 0;
    for (let index = 0; index < samples.length; index += 1) energy += samples[index] * samples[index];
    const rms = Math.sqrt(energy / Math.max(1, samples.length));
    peak = Math.max(peak, rms);
    try {
      onLevel(rms, peak);
    } catch {
      // A UI callback must never break capture.
    }
  };

  let node = null;
  let mode = "worklet";
  try {
    if (!context.audioWorklet) throw new Error("AudioWorklet unavailable");
    await loadWorklet(context);
    node = new AudioWorkletNode(context, "bolo-level-meter", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1]
    });
    node.port.onmessage = (event) => {
      const data = event.data;
      if (data && data.samples) collect(data.samples);
    };
    node.connect(mute);
  } catch {
    mode = "script";
    node = context.createScriptProcessor(4096, 1, 1);
    node.onaudioprocess = (event) => collect(event.inputBuffer.getChannelData(0));
    node.connect(mute);
  }
  source.connect(node);

  const cleanup = () => {
    clearTimeout(timer);
    try { if (node && node.port) node.port.close(); } catch { /* already closed */ }
    try { if (node) node.disconnect(); } catch { /* already disconnected */ }
    try { source.disconnect(); } catch { /* already disconnected */ }
    try { mute.disconnect(); } catch { /* already disconnected */ }
    stream.getTracks().forEach((item) => item.stop());
  };

  const controller = {
    mode,
    sampleRate: context.sampleRate,
    deviceLabel: track ? track.label : "",
    peak: () => peak,
    async stop({ discard = false } = {}) {
      if (stopped) return null;
      stopped = true;
      cleanup();
      if (discard || chunks.length === 0) return null;
      const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
      const joined = new Float32Array(length);
      let offset = 0;
      for (const chunk of chunks) {
        joined.set(chunk, offset);
        offset += chunk.length;
      }
      return pcm16ToWav(resampleTo16k(joined, context.sampleRate), TARGET_RATE);
    },
    async cancel() {
      if (stopped) return;
      stopped = true;
      cleanup();
    }
  };

  const timer = setTimeout(() => {
    if (stopped) return;
    controller.stop().then((blob) => {
      if (blob) onMaxStop(blob);
    });
  }, maxMs);

  return controller;
}
