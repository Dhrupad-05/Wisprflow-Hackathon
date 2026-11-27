const state = { connected: true, currentPortal: "none", lastFills: [] };
const broadcast = () => chrome.runtime.sendMessage({ type: "STATE", state }).catch(() => {});
chrome.runtime.onInstalled.addListener(() => chrome.storage.local.set({ state }));
chrome.action?.onClicked.addListener((tab) => { if (tab.windowId !== undefined) chrome.sidePanel.open({ windowId: tab.windowId }); });
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
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
