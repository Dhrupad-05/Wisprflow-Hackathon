const SENSITIVE_PATTERN = /otp|pin|password|cvv|cvc|aadhaar|aadhar|passcode/i;
const hostAllowed = (url) => {
  try {
    const host = new URL(url).hostname;
    return (globalThis.ALLOWED_HOSTS || []).some((domain) => host === domain || host.endsWith("." + domain));
  } catch {
    return false;
  }
};
const allowed = () => hostAllowed(location.href);
const labelText = (field) => [...document.querySelectorAll(`label[for="${CSS.escape(field.id)}"]`)].map((label) => label.textContent).join(" ");
const isSensitive = (field, registrySensitive = false) => {
  if (!field || registrySensitive) return true;
  const autocomplete = (field.getAttribute("autocomplete") || "").toLowerCase();
  const metadata = [field.type, field.name, field.id, field.getAttribute("aria-label"), labelText(field)].join(" ");
  return field.getAttribute("data-sensitive") === "true" || autocomplete.includes("one-time-code") || field.type === "password" || SENSITIVE_PATTERN.test(metadata);
};
const findField = (id) => document.querySelector(`[data-field="${CSS.escape(id)}"], [name="${CSS.escape(id)}"], #${CSS.escape(id)}`);
const fillNative = (field, value) => {
  const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  field.value = String(value ?? "");
  setter?.call(field, String(value ?? ""));
  field.setAttribute("value", String(value ?? ""));
  field.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: String(value ?? "") }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
  const script = document.createElement("script");
  script.textContent = `(${(id, next) => { const target = document.querySelector(`[data-field="${id}"], [name="${id}"], #${id}`); if (target) { target.value = next; target.dispatchEvent(new Event("input", { bubbles: true })); target.dispatchEvent(new Event("change", { bubbles: true })); } }})("${String(field.getAttribute("data-field") || field.id).replaceAll('"', '\\"')}", "${String(value ?? "").replaceAll('"', '\\"')}")`;
  (document.head || document.documentElement).appendChild(script);
  script.remove();
};
const handle = (message, source = "runtime") => {
  if (!allowed()) return { ok: false, reason: "origin-not-allow-listed" };
  const field = findField(message.field);
  if (!field) return { ok: false, reason: "field-not-found" };
  if (isSensitive(field, message.sensitive === true)) return { ok: false, reason: "sensitive-field-refused" };
  if (message.type === "FILL_FIELD") { fillNative(field, message.value); field.focus(); return { ok: true, field: message.field, type: message.type, filled: field.value === String(message.value ?? "") }; }
  if (message.type === "HIGHLIGHT") { field.focus(); field.scrollIntoView({ block: "center" }); field.style.outline = "4px solid #3157d5"; return { ok: true, field: message.field, type: message.type }; }
  return { ok: false, reason: "unsupported-message" };
};

function requestOpenSite(message) {
  if (!hostAllowed(message.url)) return Promise.resolve({ ok: false, reason: "origin-not-allow-listed" });
  return chrome.runtime.sendMessage({ type: "OPEN_SITE", url: message.url, portal_id: message.portal_id, mode: message.mode }).catch(() => ({ ok: false, reason: "extension-unavailable" }));
}

/* ---------------- Floating bubble (Shadow DOM) ---------------- */

const BUBBLE_ID = "bolo-bubble-host";
const bubbleState = { status: "idle", prompt: "", transcript: "", lang: "en", fields: [], error: "", open: false, lastPrompt: "" };

function apiBase() {
  return /^(localhost|127\.0\.0\.1)$/.test(location.hostname) ? location.origin : "";
}

function scanPage() {
  const fields = globalThis.BOLO_SCAN ? globalThis.BOLO_SCAN(document) : [];
  bubbleState.fields = fields;
  renderBubble();
  chrome.runtime.sendMessage({ type: "PAGE_SCHEMA", fields, base: apiBase(), url: location.href }).catch(() => {});
}

function renderBubble() {
  const host = document.getElementById(BUBBLE_ID);
  if (!host || !host.shadowRoot) return;
  const root = host.shadowRoot;
  const set = (id, text) => { const node = root.getElementById(id); if (node) node.textContent = text; };
  const bubble = root.getElementById("bubble");
  if (bubble) {
    bubble.dataset.state = bubbleState.status;
    bubble.setAttribute("aria-label", `Bolo assistant: ${bubbleState.status}. Tap to open.`);
    bubble.textContent = bubbleState.status === "listening" ? "◉" : bubbleState.status === "thinking" ? "…" : bubbleState.status === "error" ? "!" : "🎙";
  }
  set("prompt", bubbleState.prompt || "Tap the bubble to ask Bolo.");
  set("heard", bubbleState.transcript ? `“${bubbleState.transcript}”` : "");
  set("status", bubbleState.error || bubbleState.status);
  const sensitive = bubbleState.fields.filter((field) => field.sensitive).length;
  set("fields", `${bubbleState.fields.length} fields · ${sensitive} sensitive · ${bubbleState.lang.toUpperCase()}`);
  const panel = root.getElementById("panel");
  if (panel) panel.hidden = !bubbleState.open;
}

function speakBubble() {
  if (!bubbleState.prompt || bubbleState.prompt === bubbleState.lastPrompt) return;
  bubbleState.lastPrompt = bubbleState.prompt;
  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(bubbleState.prompt);
    utterance.lang = { en: "en-IN", hi: "hi-IN", bn: "bn-IN" }[bubbleState.lang] || "en-IN";
    window.speechSynthesis.speak(utterance);
  } catch {
    // Speech is optional; the prompt is always visible.
  }
}

function sendBolo(type, extra = {}) {
  chrome.runtime.sendMessage({ type, ...extra }).catch(() => {
    bubbleState.status = "error";
    bubbleState.error = "The extension is reloading. Refresh the page.";
    renderBubble();
  });
}

function mountBubble() {
  if (document.getElementById(BUBBLE_ID)) return;
  if (location.pathname === "/" && document.getElementById("consent-gate")) return;
  const host = document.createElement("div");
  host.id = BUBBLE_ID;
  host.style.cssText = "all: initial; position: fixed; right: 20px; bottom: 20px; z-index: 2147483647;";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      .wrap { font: 14px/1.4 system-ui, sans-serif; color: #152238; }
      #bubble { width: 56px; height: 56px; border-radius: 50%; border: 0; cursor: grab; color: #fff;
        background: #1e3a8a; font-size: 22px; box-shadow: 0 8px 24px rgba(15,23,42,.35); touch-action: none; }
      #bubble[data-state="listening"] { background: #b91c1c; }
      #bubble[data-state="thinking"] { background: #b45309; }
      #bubble[data-state="speaking"] { background: #0f766e; }
      #bubble[data-state="error"] { background: #991b1b; }
      #panel { width: 290px; margin-top: 10px; background: #fff; border: 1px solid #dbe3ef; border-radius: 14px;
        padding: 12px; box-shadow: 0 12px 32px rgba(15,23,42,.25); }
      #panel[hidden] { display: none; }
      #prompt { margin: 0 0 6px; font-weight: 600; }
      #heard { margin: 0 0 8px; color: #475569; min-height: 18px; }
      #status, #fields { margin: 0 0 8px; font-size: 12px; color: #64748b; }
      .row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
      button { min-height: 34px; padding: 0 10px; border-radius: 9px; border: 1px solid #cbd5e1; background: #f8fafc; cursor: pointer; }
      button.primary { background: #1e3a8a; color: #fff; border-color: #1e3a8a; }
      input, select { min-height: 34px; padding: 0 8px; border: 1px solid #cbd5e1; border-radius: 9px; font: inherit; }
      input { flex: 1; min-width: 0; }
    </style>
    <div class="wrap">
      <button id="bubble" data-state="idle" aria-label="Bolo assistant">🎙</button>
      <section id="panel" hidden>
        <p id="prompt">Tap the bubble to ask Bolo.</p>
        <p id="heard"></p>
        <p id="status">idle</p>
        <p id="fields">0 fields</p>
        <div class="row">
          <button id="yes" class="primary">Yes</button>
          <button id="no">No</button>
          <button id="repeat">Repeat</button>
          <button id="stop">Stop</button>
        </div>
        <div class="row">
          <select id="lang" aria-label="Language"><option value="en">English</option><option value="hi">हिन्दी</option><option value="bn">বাংলা</option></select>
          <input id="typed" placeholder="Type instead" aria-label="Type your answer">
          <button id="send" class="primary">Send</button>
        </div>
      </section>
    </div>`;
  document.documentElement.appendChild(host);
  const q = (id) => root.getElementById(id);

  q("bubble").addEventListener("click", () => {
    if (host.dataset.dragged === "1") { host.dataset.dragged = "0"; return; }
    bubbleState.open = !bubbleState.open;
    renderBubble();
    if (bubbleState.open) scanPage();
  });
  q("yes").addEventListener("click", () => sendBolo("BOLO_TEXT", { text: "yes" }));
  q("no").addEventListener("click", () => sendBolo("BOLO_TEXT", { text: "no" }));
  q("repeat").addEventListener("click", () => sendBolo("BOLO_TEXT", { text: "repeat" }));
  q("stop").addEventListener("click", () => {
    try { window.speechSynthesis.cancel(); } catch { /* no-op */ }
    bubbleState.status = "idle";
    renderBubble();
    sendBolo("BOLO_STOP");
  });
  q("lang").addEventListener("change", (event) => sendBolo("BOLO_LANG", { lang: event.target.value }));
  const submitTyped = () => {
    const value = q("typed").value.trim();
    if (!value) return;
    q("typed").value = "";
    bubbleState.transcript = value;
    bubbleState.status = "thinking";
    renderBubble();
    sendBolo("BOLO_TEXT", { text: value });
  };
  q("send").addEventListener("click", submitTyped);
  q("typed").addEventListener("keydown", (event) => { if (event.key === "Enter") submitTyped(); });

  // Drag the bubble; a drag does not toggle the panel.
  let drag = null;
  q("bubble").addEventListener("pointerdown", (event) => {
    drag = { x: event.clientX, y: event.clientY };
    q("bubble").setPointerCapture(event.pointerId);
  });
  q("bubble").addEventListener("pointermove", (event) => {
    if (!drag) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) < 6) return;
    host.dataset.dragged = "1";
    const right = Math.max(8, window.innerWidth - event.clientX - 28);
    const bottom = Math.max(8, window.innerHeight - event.clientY - 28);
    host.style.right = `${right}px`;
    host.style.bottom = `${bottom}px`;
  });
  q("bubble").addEventListener("pointerup", () => { drag = null; });

  renderBubble();
  scanPage();
  setInterval(scanPage, 3000);
  let scanTimer = null;
  new MutationObserver(() => {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(scanPage, 800);
  }).observe(document.body, { childList: true, subtree: true });
  let lastUrl = location.href;
  setInterval(() => {
    if (location.href !== lastUrl) { lastUrl = location.href; scanPage(); }
  }, 1000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mountBubble);
} else {
  mountBubble();
}

/* ---------------- Messaging ---------------- */

window.addEventListener("message", (event) => {
  if (event.source !== window || event.origin !== location.origin || !event.data || event.data.source !== "bolo-sahayak") return;
  if (event.data.type === "OPEN_SITE") {
    requestOpenSite(event.data).then((result) => window.postMessage({ source: "bolo-sahayak-extension", type: "OPEN_SITE_RESULT", ...result }, location.origin));
    return;
  }
  if (event.data.type === "SESSION") {
    chrome.runtime.sendMessage({ type: "BOLO_SESSION", session_id: event.data.session_id, base: apiBase() }).catch(() => {});
    return;
  }
  const field = findField(event.data.field);
  const guard = !allowed() ? { ok: false, reason: "origin-not-allow-listed" } : !field ? { ok: false, reason: "field-not-found" } : isSensitive(field, event.data.sensitive === true) ? { ok: false, reason: "sensitive-field-refused" } : null;
  if (guard) { window.postMessage({ source: "bolo-sahayak-extension", ...guard }, location.origin); return; }
  if (event.data.type === "FILL_FIELD") { chrome.runtime.sendMessage({ type: "MAIN_FILL", field: event.data.field, value: event.data.value }).then((result) => window.postMessage({ source: "bolo-sahayak-extension", ...result }, location.origin)); return; }
  window.postMessage({ source: "bolo-sahayak-extension", ...handle(event.data, "window") }, location.origin);
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "GUIDE_CLICK") {
    const buttons = [...document.querySelectorAll("button, [role='button'], input[type='submit'], a[href]")]
      .filter((button) => button.offsetParent && !button.disabled);
    const target = buttons.find((button) => /next|continue|proceed|submit|apply|\u0906\u0917\u0947/i.test(button.textContent || "")) || buttons[0];
    if (!target) { sendResponse({ ok: false, reason: "no-button" }); return true; }
    target.scrollIntoView({ block: "center" });
    target.style.outline = "4px solid #f59e0b";
    const label = (target.textContent || target.getAttribute("aria-label") || "button").trim().slice(0, 80);
    try {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(label));
    } catch { /* speech is optional */ }
    sendResponse({ ok: true, label });
    return true;
  }
  if (message.type === "SUBMIT") {
    const button = document.querySelector("form[data-step='otp'] button, form[data-step='review'] button");
    if (button) button.click();
    sendResponse({ ok: Boolean(button) });
    return true;
  }
  if (message.type === "BOLO_STATE") {
    Object.assign(bubbleState, message.state || {});
    renderBubble();
    if (bubbleState.prompt) speakBubble();
    sendResponse({ ok: true });
    return true;
  }
  sendResponse(handle(message));
});
