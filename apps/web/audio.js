export function floatToPcm16(samples) {
  const output = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const value = Math.max(-1, Math.min(1, samples[index]));
    output[index] = value < 0 ? value * 0x8000 : value * 0x7fff;
  }
  return output;
}

export function pcm16ToWav(samples, sampleRate = 16000) {
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
  if (sourceRate === 16000) return samples;
  const ratio = sourceRate / 16000;
  const output = new Float32Array(Math.round(samples.length / ratio));
  for (let index = 0; index < output.length; index += 1) output[index] = samples[Math.min(samples.length - 1, Math.round(index * ratio))];
  return output;
}

export async function captureWav({ onEnergy = () => {}, maxMs = 120000 } = {}) {
  const permission = navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error("microphone-timeout")), 1500));
  const stream = await Promise.race([permission, timeout]);
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const chunks = [];
  processor.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0);
    chunks.push(new Float32Array(input));
    let energy = 0;
    for (const sample of input) energy += sample * sample;
    onEnergy(Math.sqrt(energy / Math.max(1, input.length)));
  };
  source.connect(processor); processor.connect(context.destination);
  let stopped = false;
  const timer = setTimeout(() => controller.stop(), maxMs);
  const controller = {
    async stop() {
      if (stopped) return null;
      stopped = true; clearTimeout(timer); processor.disconnect(); source.disconnect(); stream.getTracks().forEach((track) => track.stop()); await context.close();
      const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0); const joined = new Float32Array(length); let offset = 0;
      for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.length; }
      return pcm16ToWav(resampleTo16k(joined, context.sampleRate), 16000);
    },
  };
  return controller;
}

export function blobToBase64(blob) {
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",")[1] || ""); reader.onerror = reject; reader.readAsDataURL(blob); });
}
