import { blobToBase64, captureMicrophone, listMicrophones, microphoneAvailable, MicrophoneError } from "/audio.js";
import { BARGE_DEFAULTS, BargeInMonitor } from "/packages/voice/bargein.js";
import { END_WORDS, EndpointingEngine } from "/packages/voice/endpointing.js";
import { VAD_DEFAULTS, VoiceActivityDetector } from "/packages/voice/vad.js";

const $ = (id) => document.getElementById(id);
const LANGS = { en: "en-IN", hi: "hi-IN", bn: "bn-IN" };
const HARD_MAX_MS = 30000;

const state = {
  sid: null,
  lang: "en",
  copy: {},
  slow: false,
  privateMode: false,
  iframeLoaded: false,
  voiceWarned: false,
  privacyPending: false,
  sensitiveField: null,
  portalQueue: [],
  portalId: null,
  processing: false,
  finishing: false,
  fieldType: "short",
  health: null,
  micState: "idle",
  capture: null,
  endpoint: null,
  vad: null,
  recognition: null,
  speech: null,
  utterance: null,
  speaking: false,
  bargeIn: true,
  bargeMonitor: null,
  micGranted: false,
  liveEdited: false,
  partial: "",
  micTest: false,
  progress: null,
  field: null,
  choices: [],
  readback: null,
  lastText: null
};

const fallback = {
  greeting: "Tell me what you need.",
  consent: "This demo may send your speech to the configured speech provider. OTP, PIN, password, CVV, and full Aadhaar are never captured by voice. Do you agree?",
  agree: "Continue",
  nearby: "Is anyone near you?",
  private_hint: "If yes, use private mode. You can tap answers.",
  voice_missing: "Text is shown because a Bengali or Hindi voice is not available on this device.",
  ready: "Ready.",
  listening: "Listening… tap the mic to stop.",
  speaking: "Hearing you…",
  processing: "Thinking…",
  send: "Send",
  done: "I’m done",
  yes: "Yes",
  no: "No",
  any: "Any bank",
  cancel: "Cancel",
  slow: "Slow speaker",
  private: "Private mode",
  forget: "Forget everything",
  print: "Print masked log",
  assistant: "Assistant",
  heard: "What I heard",
  portal: "Demo portal",
  no_portal: "Your selected demo form will appear here.",
  demo: "DEMO MODE",
  mic_tap: "Tap to speak",
  mic_listening: "Listening… tap to stop",
  mic_thinking: "Thinking…",
  mic_blocked: "Microphone blocked",
  mic_test: "Mic test",
  mic_testing: "Testing the microphone for 3 seconds — please speak.",
  mic_ok: "Mic OK. Your level meter moved.",
  mic_no_sound: "Mic opened but no sound arrived. Check the input device or OS microphone privacy setting.",
  mic_permission: "Microphone permission is blocked. Allow it in the browser address bar, then tap the mic again.",
  mic_no_device: "No microphone was found. Plug one in or pick another input device.",
  mic_busy: "Another app is using the microphone. Close it and try again.",
  mic_insecure: "Microphone needs https:// or http://127.0.0.1. Open the app on localhost.",
  mic_unsupported: "This browser cannot record audio. Use the typed box below.",
  mic_error: "The microphone could not start. You can type your answer below.",
  heard_nothing: "I did not hear any words. Tap the mic and speak, or type below.",
  stt_no_key: "No server speech key is configured, so voice is running in demo mode.",
  stt_auth: "The speech key was rejected by the provider.",
  stt_timeout: "The speech service took too long.",
  stt_language: "The speech service does not support this language yet.",
  stt_audio: "The recording could not be sent. Please try again.",
  stt_offline: "The speech service could not be reached.",
  stt_failed: "Speech could not be transcribed.",
  using_browser: "Using this browser’s speech recognition.",
  type_instead: "You can type your answer below.",
  engine_wispr: "Wispr",
  engine_xai: "Server voice",
  engine_web: "Web Speech",
  engine_text: "Typed",
  engine_demo: "Demo",
  voice_ready: "Voice ready",
  demo_hint: "Demo mode: type, or use browser voice",
  network_error: "Network problem — please try again.",
  barge: "Interrupt me",
  interrupted: "Stopped speaking — listening.",
  live_label: "Live transcript — edit before it sends",
  live_placeholder: "Your words appear here…",
  live_hint: "You can fix words while speaking. Press Enter to send.",
  tagline: "Voice-first help with government forms.",
  consent_point_1: "Speak, type or tap — your choice.",
  consent_point_2: "OTP, PIN and passwords are only ever typed by you.",
  consent_point_3: "Nothing is submitted without your explicit yes.",
  step_service: "Choose",
  step_details: "Details",
  step_confirm: "Confirm",
  step_done: "Done",
  step_note: "Step {step} of {total}",
  step_field: "Field {index} of {total}",
  digit_hint: "Tap digits, then Send.",
  clear_field: "Clear",
  backspace: "Backspace",
  yes_hint: "That is correct",
  no_hint: "Change it",
  submitted: "Demo submitted.",
  fix_digits: "Fix the number",
  fix_hint: "Type or tap the correct number, then Send. I will read it back.",
  retry: "Try again",
  lang_detected: "Language switched to {language}.",
  helper_print: "Helper sheet",
  helper_title: "Helper sheet",
  helper_sensitive: "You type this yourself",
  helper_note: "No OTP, PIN, password, CVV or Aadhaar is shown on this sheet. The demo never submits without your yes.",
  helper_url: "Open this address on your helper's phone:",
  bank_hint: "Tap your bank, or say its name."
};

const setText = (id, value) => {
  if ($(id)) $(id).textContent = value;
};

const fill = (template, values) =>
  Object.entries(values).reduce(
    (out, [key, value]) => out.replaceAll(`{${key}}`, String(value)),
    String(template || "")
  );

function setStatus(text) {
  setText("status", text);
}

function setHeard(text) {
  setText("heard", text || "—");
}

function mask(text) {
  if (!state.privateMode) return text;
  return String(text).replace(/[0-9]/g, "•");
}

async function api(path, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function loadCopy(lang) {
  try {
    const response = await fetch(`/i18n/${lang}.json`);
    state.copy = response.ok ? { ...fallback, ...(await response.json()) } : fallback;
  } catch {
    state.copy = fallback;
  }
  applyCopy();
}

function applyCopy() {
  setText("consent-text", state.copy.consent);
  setText("consent-yes", state.copy.agree);
  setText("private-label", state.copy.private);
  setText("slow-label", state.copy.slow);
  setText("send", state.copy.send);
  setText("sensitive-done", state.copy.done);
  setText("wipe", state.copy.forget);
  setText("print", state.copy.print);
  setText("retry", state.copy.retry || fallback.retry);
  setText("helper", state.copy.helper_print || fallback.helper_print);
  setText("assistant-label", state.copy.assistant);
  setText("heard-label", state.copy.heard);
  setText("portal-title", state.copy.portal);
  setText("portal-empty", state.copy.no_portal);
  setText("demo-badge", state.copy.demo);
  setText("mic-test", state.copy.mic_test);
  setText("barge-label", state.copy.barge || fallback.barge);
  setText("live-label", state.copy.live_label || fallback.live_label);
  setText("live-hint", state.copy.live_hint || fallback.live_hint);
  if ($("live")) $("live").placeholder = state.copy.live_placeholder || fallback.live_placeholder;
  setText("tagline", state.copy.tagline || fallback.tagline);
  setText("consent-tagline", state.copy.tagline || fallback.tagline);
  setText("consent-point-1", state.copy.consent_point_1 || fallback.consent_point_1);
  setText("consent-point-2", state.copy.consent_point_2 || fallback.consent_point_2);
  setText("consent-point-3", state.copy.consent_point_3 || fallback.consent_point_3);
  if (state.progress) renderProgress(state.progress);
  if (state.field && $("digit-pad") && !$("digit-pad").hidden) {
    $("digit-pad").dataset.ready = "";
    renderDigitPad(state.field, state.progress && state.progress.state);
  }
  setMicState(state.micState);
}

function renderProgress(progress) {
  const data = progress || { step: 1, total: 4, field: null };
  state.progress = data;
  const list = $("stepper");
  if (!list) return;
  const names = [
    state.copy.step_service || fallback.step_service,
    state.copy.step_details || fallback.step_details,
    state.copy.step_confirm || fallback.step_confirm,
    state.copy.step_done || fallback.step_done
  ];
  const total = data.total || names.length;
  list.replaceChildren(
    ...names.slice(0, total).map((name, index) => {
      const step = index + 1;
      const item = document.createElement("li");
      item.className = `step${step < data.step ? " done" : step === data.step ? " current" : ""}`;
      if (step === data.step) item.setAttribute("aria-current", "step");
      const dot = document.createElement("span");
      dot.className = "step-dot";
      dot.setAttribute("aria-hidden", "true");
      dot.textContent = step < data.step ? "✓" : String(step);
      const label = document.createElement("span");
      label.className = "step-name";
      label.textContent = name;
      item.append(dot, label);
      return item;
    })
  );
  let note = fill(state.copy.step_note || fallback.step_note, {
    step: data.step,
    total
  });
  if (data.field && data.field.total && data.field.index) {
    note += ` · ${fill(state.copy.step_field || fallback.step_field, data.field)}`;
  }
  setText("step-note", note);
}

function renderDigitPad(field, mode = "FORM_FILLING") {
  const pad = $("digit-pad");
  if (!pad) return;
  const show = Boolean(
    mode === "FORM_FILLING" && field && field.type === "digits" && !field.sensitive
  );
  pad.hidden = !show;
  if (!show) return;
  if (pad.dataset.ready === "true") return;
  pad.dataset.ready = "true";
  const hint = document.createElement("p");
  hint.className = "digit-hint";
  hint.textContent = state.copy.digit_hint || fallback.digit_hint;
  pad.append(hint);
  ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"].forEach((digit) => {
    const key = document.createElement("button");
    key.type = "button";
    key.className = "digit";
    key.dataset.digit = digit;
    key.textContent = digit;
    key.onclick = () => appendDigit(digit);
    pad.append(key);
  });
  const back = document.createElement("button");
  back.type = "button";
  back.className = "digit";
  back.setAttribute("aria-label", state.copy.backspace || fallback.backspace);
  back.textContent = "⌫";
  back.onclick = () => {
    const input = $("text");
    if (input) input.value = input.value.slice(0, -1);
    focusText();
  };
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "digit digit-clear";
  clear.textContent = state.copy.clear_field || fallback.clear_field;
  clear.onclick = () => {
    const input = $("text");
    if (input) input.value = "";
    focusText();
  };
  pad.append(back, clear);
}

function appendDigit(digit) {
  const input = $("text");
  if (!input) return;
  input.value = `${input.value}${digit}`.slice(0, 24);
  focusText();
}

function renderAnswerTools(mode, field) {
  if (field) state.field = field;
  renderDigitPad(state.field, mode);
  renderQuickReplies(mode, state.field);
}

const ENGINE_LABELS = () => ({
  wispr: state.copy.engine_wispr,
  xai: state.copy.engine_xai,
  server: state.copy.engine_xai,
  web: state.copy.engine_web,
  typed: state.copy.engine_text,
  demo: state.copy.engine_demo
});

function setEngine(kind) {
  const badge = $("engine-badge");
  if (!badge) return;
  badge.textContent = ENGINE_LABELS()[kind] || fallback.engine_demo;
  badge.dataset.engine = kind;
}

function setMicState(mode) {
  state.micState = mode;
  const mic = $("mic");
  if (!mic) return;
  mic.className = `mic mic-${mode}`;
  mic.setAttribute("aria-pressed", mode === "listening" ? "true" : "false");
  const labels = {
    idle: state.copy.mic_tap || fallback.mic_tap,
    listening: state.copy.mic_listening || fallback.mic_listening,
    thinking: state.copy.mic_thinking || fallback.mic_thinking,
    error: state.copy.mic_blocked || fallback.mic_blocked
  };
  setText("mic-label", labels[mode] || labels.idle);
}

function renderLevel(level) {
  const percent = Math.max(0, Math.min(100, Math.round((Number(level) || 0) * 320)));
  const bar = $("level-bar");
  const meter = $("meter");
  if (bar) bar.style.width = `${percent}%`;
  if (meter) meter.setAttribute("aria-valuenow", String(percent));
  if (meter) meter.dataset.active = percent > 3 ? "true" : "false";
}

function showMicNote(text) {
  const note = $("mic-error");
  if (!note) return;
  note.hidden = !text;
  note.textContent = text || "";
}

function focusText() {
  const input = $("text");
  if (input) input.focus();
}

async function loadHealth() {
  try {
    const health = await api("/v1/health", {}, 6000);
    state.health = health;
    const chip = $("health-chip");
    if (chip) {
      const engines = Object.entries(health.stt || {})
        .filter(([, ready]) => ready)
        .map(([name]) => (name === "wispr_api" ? fallback.engine_wispr : fallback.engine_xai));
      chip.hidden = false;
      chip.dataset.mode = health.demo_mode ? "demo" : "voice";
      chip.textContent = health.voice_ready
        ? `${state.copy.voice_ready || fallback.voice_ready}: ${engines.join(", ")}`
        : state.copy.demo_hint || fallback.demo_hint;
    }
    setEngine(health.voice_ready ? (health.stt && health.stt.wispr_api ? "wispr" : "xai") : "demo");
  } catch {
    // Diagnostics are best-effort; the typed path still works.
  }
}

function stopSpeaking() {
  state.speaking = false;
  const audio = state.speech;
  state.speech = null;
  if (audio) {
    try {
      audio.pause();
      audio.currentTime = 0;
    } catch {
      // Already stopped.
    }
  }
  state.utterance = null;
  if ("speechSynthesis" in window) {
    try { speechSynthesis.cancel(); } catch { /* nothing queued */ }
  }
  stopBargeMonitor();
}

async function speak(text) {
  if (!text) return;
  stopSpeaking();
  state.speaking = true;
  try {
    const response = await fetch("/v1/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language: state.lang })
    });
    if (response.ok) {
      const audio = new Audio(URL.createObjectURL(await response.blob()));
      state.speech = audio;
      audio.addEventListener("ended", () => {
        if (state.speech !== audio) return;
        state.speech = null;
        state.speaking = false;
        stopBargeMonitor();
      });
      audio.play().then(() => {
        if (state.speech === audio) startBargeMonitor();
      }).catch(() => {
        if (state.speech === audio) state.speaking = false;
      });
      return;
    }
  } catch {
    // Fall through to the on-device voice.
  }
  if (!("speechSynthesis" in window)) {
    state.speaking = false;
    return;
  }
  const voices = speechSynthesis.getVoices();
  const wanted = state.lang === "hi" ? "hi" : state.lang === "bn" ? "bn" : "en";
  const voice = voices.find((item) => item.lang.toLowerCase().startsWith(wanted));
  if (wanted !== "en" && !voice) {
    state.speaking = false;
    if (!state.voiceWarned) {
      $("voice-note").hidden = false;
      setText("voice-note", state.copy.voice_missing);
      state.voiceWarned = true;
    }
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  if (voice) utterance.voice = voice;
  utterance.rate = state.slow ? 0.72 : 1;
  utterance.onstart = () => {
    if (state.utterance === utterance) startBargeMonitor();
  };
  utterance.onend = () => {
    if (state.utterance !== utterance) return;
    state.utterance = null;
    state.speaking = false;
    stopBargeMonitor();
  };
  state.utterance = utterance;
  speechSynthesis.cancel();
  speechSynthesis.speak(utterance);
}

function chipButton(command, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "chip";
  button.dataset.command = command;
  button.textContent = label;
  button.onclick = () => {
    if (command === "edit") {
      editAnswer();
      return;
    }
    if (command === "yes" && state.privacyPending) $("private").checked = true;
    send(command, "tap");
  };
  return button;
}

function editAnswer() {
  const box = $("text");
  const digits = String(state.readback || "").replace(/[^0-9]/g, "");
  if (box && digits) box.value = digits;
  setStatus(state.copy.fix_hint || fallback.fix_hint);
  focusText();
}

function choiceButton(command, label, hint, variant) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `choice ${"choice-" + variant}`;
  button.dataset.command = command;
  const title = document.createElement("span");
  title.textContent = label;
  const detail = document.createElement("small");
  detail.textContent = hint;
  button.append(title, detail);
  button.onclick = () => send(command, "tap");
  return button;
}

function renderQuickReplies(mode = "", field = null) {
  const target = $("quick-replies");
  if (!target) return;
  const confirming = mode === "CONFIRMING" || mode === "CONFIRMING_FIELD";
  const narrowing = mode === "NARROWING";
  target.replaceChildren();
  target.classList.toggle("choices", confirming);
  target.classList.toggle("banks", narrowing);
  const hint = $("answer-hint");
  if (hint) {
    hint.hidden = !narrowing;
    hint.textContent = narrowing ? state.copy.bank_hint || fallback.bank_hint : "";
  }
  if (confirming) {
    target.append(
      choiceButton("yes", state.copy.yes || fallback.yes, state.copy.yes_hint || fallback.yes_hint, "yes"),
      choiceButton("no", state.copy.no || fallback.no, state.copy.no_hint || fallback.no_hint, "no")
    );
    if (field && (field.type === "digits" || field.type === "amount") && !field.sensitive) {
      target.append(chipButton("edit", state.copy.fix_digits || fallback.fix_digits));
    }
    target.append(chipButton("cancel", state.copy.cancel || fallback.cancel));
    return;
  }
  if (narrowing) {
    (state.choices || []).forEach((option) => {
      target.append(chipButton(option.label, option.label));
    });
    target.append(
      chipButton("any", state.copy.any || fallback.any),
      chipButton("cancel", state.copy.cancel || fallback.cancel)
    );
    return;
  }
  [
    ["yes", state.copy.yes || fallback.yes],
    ["no", state.copy.no || fallback.no],
    ["any", state.copy.any || fallback.any],
    ["cancel", state.copy.cancel || fallback.cancel]
  ].forEach(([command, label]) => target.append(chipButton(command, label)));
}

async function switchLanguage(lang) {
  if (!LANGS[lang] || lang === state.lang) return;
  state.lang = lang;
  if ($("lang")) $("lang").value = lang;
  if ($("consent-lang")) $("consent-lang").value = lang;
  await loadCopy(lang);
  const note = $("lang-note");
  if (note) {
    note.textContent = fill(state.copy.lang_detected || fallback.lang_detected, {
      language: lang.toUpperCase()
    });
  }
}

function setControlsBusy(disabled) {
  if ($("send")) $("send").disabled = disabled;
  $("quick-replies").querySelectorAll("button").forEach((button) => {
    button.disabled = disabled;
  });
}

async function startSession() {
  const session = await api("/v1/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lang_hint: state.lang, private_mode: state.privateMode })
  });
  state.sid = session.session_id;
  $("consent-gate").hidden = true;
  $("app").hidden = false;
  setText("notice", state.copy.consent);
  setText("prompt", state.copy.greeting);
  setStatus(state.copy.ready);
  state.choices = session.choices || [];
  renderProgress(session.progress);
  renderAnswerTools(session.state || "IDLE", session.progress && session.progress.field);
  setMicState("idle");
  loadHealth();
  focusText();
  speak(state.copy.greeting);
}

async function openPortal(id) {
  state.portalId = id;
  const portal = await api(`/v1/portals/${id}`);
  const frame = $("portal-frame");
  frame.hidden = false;
  $("portal-empty").hidden = true;
  state.iframeLoaded = false;
  frame.onload = () => {
    state.iframeLoaded = true;
    if (state.sensitiveField) focusSensitive(state.sensitiveField);
    state.portalQueue.splice(0).forEach(postToPortal);
  };
  frame.src = portal.url;
}

function postToPortal(action) {
  const frame = $("portal-frame");
  if (!state.iframeLoaded) {
    state.portalQueue.push(action);
    return;
  }
  if (frame.contentWindow) frame.contentWindow.postMessage(action, location.origin);
}

function focusSensitive(field) {
  state.sensitiveField = field;
  try {
    const documentInFrame = $("portal-frame").contentDocument;
    const input = documentInFrame && documentInFrame.querySelector(`[data-field="${field}"]`);
    if (input && input.offsetParent === null) {
      // Walk the demo portal's steps so the user is typing into a visible field.
      const details = documentInFrame.querySelector("form[data-step='details'] button");
      const review = documentInFrame.querySelector("[data-step='review'] button");
      if (details) details.click();
      if (review) review.click();
    }
    if (input) {
      input.focus();
      input.classList.add("sensitive-focus");
    }
  } catch {
    // Cross-origin deployments rely on the portal's own focus.
  }
}

function handleActions(actions = [], prompt = "") {
  state.privacyPending = /is anyone near/i.test(prompt);
  if (!state.privacyPending) $("privacy-card").hidden = true;
  actions.forEach((action) => {
    if (action.type === "OPEN_PORTAL" && action.portal !== state.portalId) openPortal(action.portal);
    if (action.type === "FILL_FIELD") postToPortal(action);
    if (action.type === "AWAIT_USER_INPUT") {
      $("sensitive-done").hidden = false;
      focusSensitive(action.field);
    }
    if (action.type === "SHOW_SUMMARY") {
      $("summary").hidden = false;
      setText("summary", mask(action.masked_summary || ""));
    }
    if (action.type === "SUBMIT") {
      try {
        const documentInFrame = $("portal-frame").contentDocument;
        const button = documentInFrame && documentInFrame.querySelector("form[data-step='otp'] button");
        if (button) button.click();
        else postToPortal(action);
      } catch {
        postToPortal(action);
      }
      setStatus(state.copy.submitted || fallback.submitted);
    }
  });
  if (state.privacyPending) {
    $("privacy-card").hidden = false;
    setText("privacy-text", state.copy.nearby);
    const hint = document.createElement("p");
    hint.textContent = state.copy.private_hint;
    $("privacy-chips").replaceChildren(hint);
  }
}

async function send(text, trigger = "typed") {
  if (!state.sid || !text || state.processing) return;
  stopSpeaking();
  state.processing = true;
  setControlsBusy(true);
  $("text").value = "";
  setHeard(mask(text));
  setStatus(state.copy.processing);
  setMicState("thinking");
  try {
    const result = await api("/v1/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sid,
        transcript: text,
        lang_hint: state.lang,
        private_mode: state.privateMode,
        trigger
      })
    });
    if (result.prompt_lang && result.prompt_lang !== state.lang) {
      await switchLanguage(result.prompt_lang);
    }
    state.readback = result.readback || null;
    state.choices = result.choices || [];
    state.lastText = null;
    setText("prompt", result.prompt_text);
    setStatus(result.state);
    const field = (result.progress && result.progress.field) || null;
    state.fieldType = (field && field.type) || result.field_type || state.fieldType;
    handleActions(result.actions, result.prompt_text);
    renderProgress(result.progress);
    renderAnswerTools(result.state, field);
    speak(result.prompt_text);
    if (state.privateMode) {
      $("summary").hidden = false;
      if (result.masked_summary) setText("summary", mask(result.masked_summary));
    }
  } catch {
    state.lastText = text;
    setStatus(state.copy.network_error || fallback.network_error);
    if ($("retry")) $("retry").hidden = false;
  } finally {
    state.processing = false;
    setControlsBusy(false);
    setMicState("idle");
    focusText();
  }
}

function hasEndWord(text) {
  const lower = String(text || "").toLowerCase().trim();
  if (!lower) return null;
  for (const words of Object.values(END_WORDS)) {
    const match = words.find((word) => lower === word || lower.endsWith(` ${word}`));
    if (match) return match;
  }
  return null;
}

function sttReason(result) {
  const code = (result && result.error_code) || "empty";
  const map = {
    empty: state.copy.heard_nothing,
    missing_key: state.copy.stt_no_key,
    unauthorized: state.copy.stt_auth,
    timeout: state.copy.stt_timeout,
    unsupported_language: state.copy.stt_language,
    invalid_audio: state.copy.stt_audio,
    too_large: state.copy.stt_audio,
    offline: state.copy.stt_offline,
    client_side: state.copy.using_browser
  };
  return map[code] || state.copy.stt_failed;
}

function micErrorMessage(code) {
  const map = {
    "permission-denied": state.copy.mic_permission,
    "no-device": state.copy.mic_no_device,
    "device-busy": state.copy.mic_busy,
    "device-unavailable": state.copy.mic_no_device,
    "insecure-context": state.copy.mic_insecure,
    "unsupported-context": state.copy.mic_unsupported
  };
  return map[code] || state.copy.mic_error;
}

function showMicError(error) {
  const code = error instanceof MicrophoneError ? error.code : (error && error.code) || "microphone-error";
  const message = micErrorMessage(code);
  setMicState("error");
  setStatus(message);
  showMicNote(message);
  renderLevel(0);
  focusText();
}

function currentDeviceId() {
  const select = $("mic-device");
  return select ? select.value : undefined;
}

/* Live partial transcript: shown while listening, editable until it sends. */

function beginLiveTranscript() {
  state.liveEdited = false;
  state.partial = "";
  const wrap = $("live-wrap");
  if (wrap) wrap.hidden = false;
  const box = $("live");
  if (box) box.value = "";
}

function updatePartial(text) {
  state.partial = String(text || "");
  const box = $("live");
  if (box && !state.liveEdited) box.value = state.partial;
}

function liveText() {
  const box = $("live");
  const typed = box ? box.value.trim() : "";
  return typed || state.partial.trim();
}

function endLiveTranscript() {
  const wrap = $("live-wrap");
  if (wrap) wrap.hidden = true;
  state.liveEdited = false;
  state.partial = "";
  const box = $("live");
  if (box) box.value = "";
}

/* Voice activity, endpointing and barge-in wiring. */

function answerVad() {
  return new VoiceActivityDetector({
    threshold: VAD_DEFAULTS.threshold,
    silenceMs: VAD_DEFAULTS.silenceMs[state.fieldType] || VAD_DEFAULTS.silenceMs.short,
    minSpeechMs: 120,
    slow: state.slow
  });
}

function answerWatcher(vad) {
  return (level) => {
    renderLevel(level);
    const activity = vad.feed(level);
    if (activity.started) setStatus(state.copy.speaking || fallback.speaking);
    if (activity.ended) finishCapture("pause");
  };
}

function makeEndpoint() {
  const endpoint = new EndpointingEngine({
    slow: state.slow,
    onEnd: ({ text, reason }) => {
      endLiveTranscript();
      if (!text) return;
      setHeard(mask(text));
      send(text, reason === "end_word" ? "end_word" : "typed");
    },
    onReask: ({ text }) => {
      if (text) setHeard(mask(text));
    }
  });
  endpoint.begin({ fieldType: state.fieldType || "short", language: state.lang });
  return endpoint;
}

function stopBargeMonitor() {
  const monitor = state.bargeMonitor;
  state.bargeMonitor = null;
  if (!monitor) return;
  monitor.gate.disarm();
  monitor.onLevel = null;
  if (monitor.capture) Promise.resolve(monitor.capture.cancel()).catch(() => {});
}

/**
 * Hand the already-open barge-in microphone over to the answer flow so the
 * interruption is instant and the mic is never opened twice.
 */
function adoptBargeMonitor(monitor) {
  if (state.bargeMonitor !== monitor) return;
  state.bargeMonitor = null;
  monitor.gate.disarm();
  state.capture = monitor.capture;
  const vad = answerVad();
  state.vad = vad;
  monitor.onLevel = answerWatcher(vad);
  state.endpoint = null;
  beginLiveTranscript();
  setMicState("listening");
  setStatus(state.copy.interrupted || fallback.interrupted);
  renderLevel(0);
  state.micGranted = true;
}

function bargeLevel(monitor, level) {
  if (state.bargeMonitor !== monitor) return;
  renderLevel(level);
  if (!monitor.gate.feed(level).interrupt) return;
  // Adopt first: stopSpeaking() disarms any monitor state but must not close
  // the capture we are keeping.
  adoptBargeMonitor(monitor);
  stopSpeaking();
}

async function startBargeMonitor() {
  if (!state.bargeIn || !state.micGranted || !state.speaking || !state.sid) return;
  if (state.bargeMonitor || state.capture || state.recognition || state.micTest) return;
  const monitor = { capture: null, gate: new BargeInMonitor({ slow: state.slow }), onLevel: null };
  state.bargeMonitor = monitor;
  try {
    monitor.capture = await captureMicrophone({
      deviceId: currentDeviceId(),
      maxMs: HARD_MAX_MS,
      onLevel: (level) => {
        if (monitor.onLevel) monitor.onLevel(level);
        else bargeLevel(monitor, level);
      },
      onMaxStop: (blob) => {
        if (state.bargeMonitor === monitor) {
          stopBargeMonitor();
          return;
        }
        if (state.capture === monitor.capture) {
          state.capture = null;
          endLiveTranscript();
          handleCapturedAudio(blob, "max");
        }
      }
    });
  } catch {
    if (state.bargeMonitor === monitor) state.bargeMonitor = null;
    return;
  }
  const alive = state.bargeMonitor === monitor && state.speaking;
  if (alive) {
    monitor.gate.arm();
  } else if (state.bargeMonitor === monitor) {
    stopBargeMonitor();
  } else if (monitor.capture) {
    Promise.resolve(monitor.capture.cancel()).catch(() => {});
  }
}

function submitLive() {
  const value = liveText();
  if (!value) return;
  if (state.recognition) stopRecognition();
  const capture = state.capture;
  state.capture = null;
  if (state.endpoint) state.endpoint.cancel();
  stopBargeMonitor();
  if (capture) Promise.resolve(capture.cancel()).catch(() => {});
  endLiveTranscript();
  renderLevel(0);
  setMicState("idle");
  setHeard(mask(value));
  send(value, "typed");
}

async function populateDevices() {
  const select = $("mic-device");
  if (!select) return;
  const devices = await listMicrophones();
  if (!devices.length) {
    select.hidden = true;
    return;
  }
  select.hidden = false;
  const current = select.value;
  select.replaceChildren(
    ...devices.map((device, index) => {
      const option = document.createElement("option");
      option.value = device.id || "default";
      option.textContent = device.label || `Microphone ${index + 1}`;
      if (option.value === current) option.selected = true;
      return option;
    })
  );
}

function stopRecognition() {
  const recognition = state.recognition;
  state.recognition = null;
  if (state.endpoint) state.endpoint.cancel();
  try { if (recognition) recognition.abort(); } catch { /* already stopped */ }
  endLiveTranscript();
  setMicState("idle");
}

function recognitionFailed(code, recognition) {
  if (state.recognition === recognition) state.recognition = null;
  if (state.endpoint) state.endpoint.cancel();
  try { recognition.abort(); } catch { /* already stopped */ }
  setMicState("idle");
  setEngine("typed");
  const message = micErrorMessage(code) || state.copy.stt_failed;
  setStatus(message);
  showMicNote(`${message} ${state.copy.type_instead || fallback.type_instead}`);
  focusText();
}

function startWebSpeech(reasonMessage) {
  if (state.recognition) return;
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    setEngine("typed");
    showMicNote(`${reasonMessage} ${state.copy.type_instead || fallback.type_instead}`);
    focusText();
    return;
  }
  const recognition = new Recognition();
  state.recognition = recognition;
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.lang = LANGS[state.lang] || "en-IN";

  const endpoint = new EndpointingEngine({
    slow: state.slow,
    onEnd: ({ text, reason }) => {
      if (state.recognition === recognition) state.recognition = null;
      try { recognition.stop(); } catch { /* already stopped */ }
      const finalText = liveText() || text;
      endLiveTranscript();
      if (finalText) {
        setHeard(mask(finalText));
        send(finalText, hasEndWord(finalText) ? "end_word" : (reason === "end_word" ? "end_word" : "typed"));
      }
    },
    onReask: ({ text }) => {
      if (text) setHeard(mask(text));
    }
  });
  endpoint.begin({ fieldType: state.fieldType, language: state.lang });
  state.endpoint = endpoint;

  recognition.onresult = (event) => {
    let transcript = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      transcript += event.results[index][0].transcript;
    }
    transcript = transcript.trim();
    if (!transcript) return;
    setHeard(mask(transcript));
    updatePartial(transcript);
    const last = event.results[event.results.length - 1];
    const confidence = last && last[0] && typeof last[0].confidence === "number" ? last[0].confidence : 0.9;
    endpoint.update(transcript, confidence);
  };
  recognition.onerror = (event) => {
    const map = {
      "not-allowed": "permission-denied",
      "service-not-allowed": "permission-denied",
      "audio-capture": "no-device",
      "no-speech": "empty",
      network: "offline",
      aborted: "empty"
    };
    recognitionFailed(map[event.error] || "microphone-error", recognition);
  };
  recognition.onend = () => {
    if (state.recognition === recognition) state.recognition = null;
    if (state.endpoint) state.endpoint.cancel();
    endLiveTranscript();
    setMicState("idle");
  };

  state.micGranted = true;
  beginLiveTranscript();
  setEngine("web");
  setMicState("listening");
  setStatus(state.copy.listening);
  showMicNote(state.copy.using_browser);
  try {
    recognition.start();
  } catch {
    recognitionFailed("microphone-error", recognition);
  }
}

async function handleCapturedAudio(blob, reason) {
  if (state.finishing) return;
  state.finishing = true;
  try {
    const encoded = await blobToBase64(blob);
    let result = null;
    try {
      result = await api("/v1/stt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audio: encoded,
          language: state.lang,
          dictionary_context: ["SBI", "Kisan Credit Card", "Udyam", "PM-KISAN"]
        })
      }, 25000);
    } catch {
      result = { text: "", adapter: "none", error_code: "offline" };
    }
    const text = String((result && result.text) || "").trim();
    if (text) {
      const adapter = result.adapter;
      setEngine(adapter === "wispr_api" ? "wispr" : adapter === "xai_stt" ? "xai" : "server");
      showMicNote("");
      setHeard(text);
      send(text, hasEndWord(text) ? "end_word" : "typed");
      return;
    }
    const message = sttReason(result);
    setStatus(message);
    setMicState("idle");
    startWebSpeech(message);
  } finally {
    state.finishing = false;
  }
}

async function finishCapture(reason = "pause") {
  const capture = state.capture;
  if (!capture) return;
  state.capture = null;
  stopBargeMonitor();
  if (state.endpoint) state.endpoint.cancel();
  renderLevel(0);
  // An edited live transcript wins over the audio: the user already corrected it.
  const edited = state.liveEdited ? liveText() : "";
  endLiveTranscript();
  let blob = null;
  try {
    blob = await capture.stop({ discard: Boolean(edited) });
  } catch {
    blob = null;
  }
  if (edited) {
    setHeard(mask(edited));
    send(edited, "typed");
    return;
  }
  if (!blob) {
    const message = state.copy.heard_nothing || fallback.heard_nothing;
    setStatus(message);
    setMicState("idle");
    startWebSpeech(message);
    return;
  }
  setMicState("thinking");
  setStatus(state.copy.processing);
  await handleCapturedAudio(blob, reason);
  setMicState("idle");
}

async function startMicrophone() {
  if (!state.sid || state.processing || state.finishing || state.micTest) return;
  if (state.capture) {
    await finishCapture("tap");
    return;
  }
  if (state.recognition) {
    stopRecognition();
    return;
  }
  // A tap during playback is a barge-in: keep the open mic and stop the voice.
  const monitor = state.bargeMonitor;
  if (monitor && monitor.capture) {
    adoptBargeMonitor(monitor);
    stopSpeaking();
    setStatus(state.copy.listening);
    return;
  }
  stopSpeaking();
  if (!microphoneAvailable()) {
    showMicError(new MicrophoneError(window.isSecureContext ? "unsupported-context" : "insecure-context"));
    return;
  }
  showMicNote("");
  state.endpoint = makeEndpoint();
  const vad = answerVad();
  state.vad = vad;

  setMicState("listening");
  setStatus(state.copy.listening);
  renderLevel(0);
  beginLiveTranscript();
  try {
    state.capture = await captureMicrophone({
      deviceId: currentDeviceId(),
      maxMs: HARD_MAX_MS,
      onLevel: answerWatcher(vad),
      onMaxStop: (blob) => {
        state.capture = null;
        endLiveTranscript();
        handleCapturedAudio(blob, "max");
      }
    });
    state.micGranted = true;
    populateDevices();
  } catch (error) {
    state.capture = null;
    endLiveTranscript();
    showMicError(error);
  }
}

async function runMicTest() {
  if (state.micTest) return;
  if (state.capture) await finishCapture("tap");
  if (state.recognition) stopRecognition();
  if (!microphoneAvailable()) {
    showMicError(new MicrophoneError(window.isSecureContext ? "unsupported-context" : "insecure-context"));
    return;
  }
  state.micTest = true;
  const note = $("mic-test-state");
  note.hidden = false;
  note.textContent = state.copy.mic_testing || fallback.mic_testing;
  let capture = null;
  let peak = 0;
  try {
    capture = await captureMicrophone({
      deviceId: $("mic-device") ? $("mic-device").value : undefined,
      maxMs: 5000,
      onLevel: (level) => {
        peak = Math.max(peak, level);
        renderLevel(level);
      }
    });
    populateDevices();
    await new Promise((resolve) => setTimeout(resolve, 3000));
    if (peak < 0.01) {
      note.textContent = state.copy.mic_no_sound || fallback.mic_no_sound;
      setMicState("error");
    } else {
      note.textContent = state.copy.mic_ok || fallback.mic_ok;
      setMicState("idle");
    }
  } catch (error) {
    note.hidden = true;
    showMicError(error);
  } finally {
    if (capture) await capture.stop({ discard: true });
    renderLevel(0);
    state.micTest = false;
  }
}

$("consent-lang").onchange = async (event) => {
  state.lang = event.target.value;
  $("lang").value = state.lang;
  await loadCopy(state.lang);
  loadHealth();
};
$("lang").onchange = async (event) => {
  state.lang = event.target.value;
  $("consent-lang").value = state.lang;
  await loadCopy(state.lang);
  loadHealth();
};
$("consent-yes").onclick = () => {
  startSession().catch(() => setStatus(state.copy.network_error));
};
$("turn-form").onsubmit = (event) => {
  event.preventDefault();
  send($("text").value.trim());
};
$("private").onchange = (event) => {
  state.privateMode = event.target.checked;
  document.body.classList.toggle("private", state.privateMode);
};
$("slow").onchange = (event) => {
  state.slow = event.target.checked;
};
$("sensitive-done").onclick = () => {
  $("sensitive-done").hidden = true;
  send("ho gaya", "tap");
};
$("mic").onclick = () => {
  startMicrophone();
};
$("mic-test").onclick = () => {
  runMicTest();
};
$("mic-device").onchange = () => {
  if (state.capture) finishCapture("tap");
};
const liveBox = $("live");
if (liveBox) {
  liveBox.addEventListener("input", () => {
    state.liveEdited = true;
  });
  liveBox.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitLive();
    }
  });
}
if ($("barge-in")) {
  $("barge-in").onchange = (event) => {
    state.bargeIn = event.target.checked;
    if (!state.bargeIn) stopBargeMonitor();
  };
}
$("wipe").onclick = async () => {
  if (state.capture) await finishCapture("tap");
  if (state.recognition) stopRecognition();
  stopSpeaking();
  endLiveTranscript();
  if (state.sid) {
    try {
      await fetch(`/v1/session/${state.sid}/wipe`, { method: "POST" });
    } catch {
      // The local session is cleared regardless.
    }
  }
  state.sid = null;
  $("app").hidden = true;
  $("consent-gate").hidden = false;
  setText("prompt", "");
  setHeard("—");
  $("summary").hidden = true;
  setMicState("idle");
};
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

async function printHelper() {
  if (!state.sid) return;
  let sheet;
  try {
    sheet = await api(`/v1/session/${state.sid}/helper`);
  } catch {
    return;
  }
  const popup = window.open("", "_blank");
  if (!popup) return;
  const copy = state.copy;
  const title = copy.helper_title || fallback.helper_title;
  const steps = (sheet.steps || [])
    .map((step) => {
      const note = step.sensitive
        ? `<em>${escapeHtml(copy.helper_sensitive || fallback.helper_sensitive)}</em>`
        : "";
      return `<li>${step.filled ? "\u2611" : "\u2610"} <strong>${escapeHtml(step.label)}</strong> ${note}</li>`;
    })
    .join("");
  const address = `${location.origin}${sheet.url || "/"}`;
  popup.document.write(
    `<!doctype html><html lang="${escapeHtml(sheet.language || state.lang)}"><head><meta charset="utf-8">` +
      `<title>${escapeHtml(title)}</title><style>` +
      `body{font-family:system-ui,sans-serif;font-size:20px;line-height:1.6;margin:28px;color:#101828}` +
      `h1{font-size:30px;margin:0 0 6px}ol{font-size:22px;padding-left:28px}li{margin:10px 0}` +
      `em{font-size:16px;color:#92400e;font-style:normal}code{font-size:20px;background:#eef2fb;padding:4px 8px;border-radius:8px}` +
      `.note{font-size:16px;color:#475467}@media print{body{margin:12mm}}</style></head><body>` +
      `<h1>${escapeHtml(title)}</h1>` +
      (sheet.title ? `<p class="note">${escapeHtml(sheet.title)}</p>` : "") +
      `<ol>${steps}</ol>` +
      `<p class="note">${escapeHtml(copy.helper_url || fallback.helper_url)} <code>${escapeHtml(address)}</code></p>` +
      `<p class="note">${escapeHtml(copy.helper_note || fallback.helper_note)}</p>` +
      `</body></html>`
  );
  popup.document.close();
  popup.focus();
  popup.print();
}

$("helper").onclick = () => {
  printHelper();
};
$("retry").onclick = () => {
  $("retry").hidden = true;
  const text = state.lastText;
  if (text) send(text);
};

$("print").onclick = async () => {
  if (!state.sid) return;
  const log = await api(`/v1/session/${state.sid}/log`);
  const popup = window.open("", "_blank");
  if (!popup) return;
  const items = (log.events || [])
    .map((event) => `<li><strong>${String(event.kind || "Event").replaceAll("_", " ")}</strong><br>${String(event.text || event.state || "Recorded interaction").replaceAll("<", "&lt;")}</li>`)
    .join("");
  popup.document.write(`<title>Bolo Sahayak · masked log</title><h1>Bolo Sahayak masked log</h1><p>No OTP, PIN, password or raw transcript is printed.</p><ol>${items}</ol>`);
  popup.print();
};
const noticeToggle = $("notice-toggle");
if (noticeToggle) {
  noticeToggle.onclick = () => {
    const body = $("notice");
    const open = body.hidden;
    body.hidden = !open;
    noticeToggle.setAttribute("aria-expanded", String(open));
  };
}

loadCopy("en");
loadHealth();

if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
