/**
 * Microphone capture worklet: forwards mono PCM blocks and live RMS to the
 * page instead of the deprecated ScriptProcessor path.
 */
class BoloLevelMeter extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input || input.length === 0) return true;
    let energy = 0;
    for (let index = 0; index < input.length; index += 1) {
      energy += input[index] * input[index];
    }
    const samples = new Float32Array(input);
    this.port.postMessage(
      { rms: Math.sqrt(energy / input.length), samples },
      [samples.buffer]
    );
    return true;
  }
}

registerProcessor("bolo-level-meter", BoloLevelMeter);
