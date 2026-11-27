/**
 * Pure speech-to-text fallback policy.
 *
 * Kept dependency-free and DOM-free so the same rules can be unit tested with
 * Node and used by the browser app. The rule that matters most: never open a
 * second microphone session while the server still has an engine to try.
 */

const CLOUD_MARKERS = new Set(["web_speech", "text"]);

export function engineReady(health) {
  const stt = (health && health.stt) || {};
  return Object.entries(stt).some(
    ([name, value]) => !CLOUD_MARKERS.has(name) && (value === true || value === "ready")
  );
}

export function readyEngineNames(health) {
  const stt = (health && health.stt) || {};
  return Object.entries(stt)
    .filter(([name, value]) => !CLOUD_MARKERS.has(name) && (value === true || value === "ready"))
    .map(([name]) => name);
}

/** True when whisper_local ran this request and legitimately heard nothing. */
export function whisperHeardNothing(result) {
  if (!result) return false;
  const tried = result.tried || [];
  if (!tried.includes("whisper_local")) return false;
  const errors = result.errors || [];
  const whisperEmpty = errors.some(
    (item) => item && item.adapter === "whisper_local" && item.error === "empty"
  );
  const whisperText = String(result.text || "").trim();
  return whisperEmpty || (result.adapter === "whisper_local" && !whisperText);
}

export function serverEngineReady(result, health) {
  if (result && typeof result.server_engine_ready === "boolean") {
    return result.server_engine_ready;
  }
  return engineReady(health);
}

/**
 * Map every SpeechRecognition error name to its own code and copy key.
 * `detail` is shown verbatim under the status so a demo failure is diagnosable.
 */
export function speechErrorInfo(name) {
  const value = String(name || "microphone-error");
  const table = {
    "not-allowed": { code: "permission-denied", key: "mic_permission" },
    "service-not-allowed": { code: "service-not-allowed", key: "mic_service_blocked" },
    "audio-capture": { code: "no-device", key: "mic_no_device" },
    "no-speech": { code: "empty", key: "heard_nothing" },
    network: { code: "offline", key: "stt_offline" },
    "language-not-supported": { code: "language-not-supported", key: "mic_language" },
    aborted: { code: "aborted", key: "mic_aborted" },
    "invalid-state": { code: "invalid-state", key: "mic_invalid_state" }
  };
  const mapped = table[value] || { code: "microphone-error", key: "mic_error" };
  return { ...mapped, detail: `SpeechRecognition: ${value}` };
}
