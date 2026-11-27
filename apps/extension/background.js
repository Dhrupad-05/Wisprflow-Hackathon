importScripts("allowlist.js");

const state = { connected: true, currentPortal: "none", lastFills: [], sessionId: null, apiBase: "http://127.0.0.1:8000", lang: "en", prompt: "", pageFields: [] };
const bolo = { status: "idle", prompt: "", transcript: "", error: "" };
const hostAllowed = (url) => {
  try {
    const host = new URL(url).hostname;
    return (globalThis.ALLOWED_HOSTS || []).some((domain) => host === domain || host.endsWith("." + domain));
  } catch {
    return false;
  }
};
const broadcast = () => chrome.runtime.sendMessage({ type: "STATE", state }).catch(() => {});
chrome.runtime.onInstalled.addListener(() => chrome.storage.local.set({ state }));

const broadcastBolo = (extra = {}) => {
  Object.assign(bolo, extra);
  const message = { type: "BOLO_STATE", state: { ...bolo, fields: state.pageFields, lang: state.lang } };
  chrome.runtime.sendMessage(message).catch(() => {});
  chrome.tabs.query({}).then((tabs) => tabs.forEach((tab) => tab.id !== undefined && chrome.tabs.sendMessage(tab.id, message).catch(() => {})));
};

async function boloTurn(text) {
  const base = (state.apiBase || "http://127.0.0.1:8000").replace(/\/$/, "");
  broadcastBolo({ status: "thinking", transcript: text, error: "" });
  try {
    if (!state.sessionId) {
      const created = await fetch(base + "/v1/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lang_hint: state.lang }) }).then((response) => response.json());
      state.sessionId = created.session_id;
    }
    const response = await fetch(base + "/v1/turn", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: state.sessionId, transcript: text, lang_hint: state.lang }) });
    if (!response.ok) throw new Error(`turn ${response.status}`);
    const result = await response.json();
    await applyBoloResult(base, result);
  } catch {
    broadcastBolo({ status: "error", error: "Bolo could not reach the assistant. Is the server running?" });
  }
}

async function applyBoloResult(base, result) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const tabId = tab && tab.id;
  const wantsFill = (result.actions || []).some((action) => action.type === "FILL_FIELD");
  if (wantsFill && !(state.pageFields || []).length) {
    broadcastBolo({ status: "error", error: "I cannot see the form fields on this page. Use the field labels and type yourself." });
    return;
  }
  for (const action of result.actions || []) {
    if (action.type === "FILL_FIELD" && tabId !== undefined) {
      chrome.tabs.sendMessage(tabId, { type: "FILL_FIELD", field: action.field, value: action.value }).catch(() => {});
    }
    if (action.type === "AWAIT_USER_INPUT" && tabId !== undefined) {
      chrome.tabs.sendMessage(tabId, { type: "HIGHLIGHT", field: action.field, sensitive: true }).catch(() => {});
    }
    if (action.type === "OPEN_SITE" && hostAllowed(action.url)) {
      chrome.tabs.create({ url: action.url }).catch(() => {});
    }
    if (action.type === "SUBMIT" && tab && tab.url && /^(https?:\/\/)?(localhost|127\.0\.0\.1)[:/]/.test(tab.url)) {
      // Real bank sites are never auto-submitted; only the local mock portals.
      chrome.tabs.sendMessage(tabId, { type: "SUBMIT" }).catch(() => {});
    }
  }
  state.prompt = result.prompt_text;
  broadcastBolo({ status: "speaking", prompt: result.prompt_text, error: "" });
  setTimeout(() => broadcastBolo({ status: "idle" }), 2500);
}

async function mapPageFields() {
  if (!state.pageFields.length) return;
  try {
    const base = (state.apiBase || "http://127.0.0.1:8000").replace(/\/$/, "");
    const response = await fetch(base + "/v1/page/fields", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: state.pageFields, language: state.lang }),
    });
    if (!response.ok) return;
    const data = await response.json();
    state.pageMap = data.fields || [];
    state.pageFields = (state.pageFields || []).map((field) => {
      const mapped = (data.fields || []).find((item) => item.field === field.id);
      return mapped ? { ...field, label: mapped.label, sensitive: mapped.sensitive } : field;
    });
    broadcastBolo({ status: bolo.status });
  } catch {
    // Field labels stay as scanned when the mapper is unreachable.
  }
}

const onBoloMessage = (message, sender, sendResponse) => {
  if (message.type === "BOLO_SESSION") {
    state.sessionId = message.session_id || state.sessionId;
    if (message.base) state.apiBase = message.base;
    sendResponse({ ok: true });
    return true;
  }
  if (message.type === "BOLO_LANG") {
    state.lang = ["en", "hi", "bn"].includes(message.lang) ? message.lang : "en";
    broadcastBolo({ status: "idle" });
    sendResponse({ ok: true });
    return true;
  }
  if (message.type === "BOLO_STOP") {
    broadcastBolo({ status: "idle", error: "" });
    sendResponse({ ok: true });
    return true;
  }
  if (message.type === "BOLO_TEXT") {
    const text = String(message.text || "").slice(0, 500);
    if (/where.*(click|tap)|kahan.*(click|tap)|\u0915\u0939\u093e\u0901.*\u0915\u094d\u0932\u093f\u0915|\u0995\u09cb\u09a5\u09be\u09df.*\u0995\u09cd\u09b2\u09bf\u0995/i.test(text)) {
      chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => tab && tab.id !== undefined && chrome.tabs.sendMessage(tab.id, { type: "GUIDE_CLICK" }).catch(() => {}));
      broadcastBolo({ status: "speaking", prompt: "I highlighted the next button. Press it yourself when ready." });
      sendResponse({ ok: true });
      return true;
    }
    if (text) boloTurn(text);
    sendResponse({ ok: true });
    return true;
  }
  if (message.type === "PAGE_SCHEMA") {
    state.pageFields = Array.isArray(message.fields) ? message.fields.slice(0, 200) : [];
    if (message.base) state.apiBase = message.base;
    mapPageFields();
    sendResponse({ ok: true, fields: state.pageFields.length });
    return true;
  }
  return false;
};
chrome.action?.onClicked.addListener((tab) => { if (tab.windowId !== undefined) chrome.sidePanel.open({ windowId: tab.windowId }); });
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (onBoloMessage(message, sender, sendResponse)) return true;
  if (message.type === "OPEN_SITE") {
    if (!hostAllowed(message.url)) { sendResponse({ ok: false, reason: "origin-not-allow-listed" }); return false; }
    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
      const properties = { url: message.url };
      if (tab && tab.id !== undefined) properties.index = tab.index + 1;
      return chrome.tabs.create(properties);
    }).then((tab) => {
      state.currentPortal = message.portal_id || message.url;
      chrome.storage.local.set({ state });
      broadcast();
      sendResponse({ ok: true, tabId: tab.id, url: message.url });
    }).catch(() => sendResponse({ ok: false, reason: "tab-create-failed" }));
    return true;
  }
  if (message.type === "MAIN_FILL") {
    if (sender.tab?.id === undefined) { sendResponse({ ok: false, reason: "no-active-tab" }); return false; }
    chrome.scripting.executeScript({ target: { tabId: sender.tab.id }, world: "MAIN", func: (fieldId, value) => { const field = document.querySelector(`[data-field="${CSS.escape(fieldId)}"], [name="${CSS.escape(fieldId)}"], #${CSS.escape(fieldId)}`); if (!field) return { ok: false, reason: "field-not-found" }; const next = String(value ?? ""); const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set; setter?.call(field, next); field.value = next; field.setAttribute("value", next); setTimeout(() => { field.value = next; }, 0); field.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: next })); field.dispatchEvent(new Event("change", { bubbles: true })); field.focus(); return { ok: true, field: fieldId, type: "FILL_FIELD", filled: field.value === next }; }, args: [message.field, message.value] }).then(([result]) => sendResponse(result.result)).catch(() => sendResponse({ ok: false, reason: "main-world-fill-failed" }));
    return true;
  }
  if (message.type === "STATE") { Object.assign(state, message.state || {}); chrome.storage.local.set({ state }); broadcast(); sendResponse({ ok: true }); return true; }
  if (message.type === "FILL_FIELD" || message.type === "HIGHLIGHT" || message.type === "PING") {
    const target = sender.tab?.id;
    if (target === undefined) { sendResponse({ ok: false, reason: "no-active-tab" }); return false; }
    chrome.tabs.sendMessage(target, message).then(sendResponse).catch(() => sendResponse({ ok: false, reason: "content-script-unavailable" }));
    return true;
  }
  sendResponse({ ok: false, reason: "unsupported-message" });
  return false;
});
