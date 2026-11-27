const SENSITIVE_PATTERN = /otp|pin|password|cvv|cvc|aadhaar|aadhar|passcode/i;
const allowed = () => ALLOWED_HOSTS.includes(location.hostname);
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
const relay = (message, source = "runtime") => { if (source === "window") window.postMessage({ source: "bolo-sahayak-extension", ...message }, location.origin); else chrome.runtime.sendMessage(message); };
const handle = (message, source = "runtime") => {
  if (!allowed()) return { ok: false, reason: "origin-not-allow-listed" };
  const field = findField(message.field);
  if (!field) return { ok: false, reason: "field-not-found" };
  if (isSensitive(field, message.sensitive === true)) return { ok: false, reason: "sensitive-field-refused" };
  if (message.type === "FILL_FIELD") { fillNative(field, message.value); field.focus(); return { ok: true, field: message.field, type: message.type, filled: field.value === String(message.value ?? "") }; }
  if (message.type === "HIGHLIGHT") { field.focus(); field.style.outline = "4px solid #3157d5"; return { ok: true, field: message.field, type: message.type }; }
  return { ok: false, reason: "unsupported-message" };
};

window.addEventListener("message", (event) => {
  if (event.source !== window || event.origin !== location.origin || !event.data || event.data.source !== "bolo-sahayak") return;
  const field = findField(event.data.field);
  const guard = !allowed() ? { ok: false, reason: "origin-not-allow-listed" } : !field ? { ok: false, reason: "field-not-found" } : isSensitive(field, event.data.sensitive === true) ? { ok: false, reason: "sensitive-field-refused" } : null;
  if (guard) { window.postMessage({ source: "bolo-sahayak-extension", ...guard }, location.origin); return; }
  if (event.data.type === "FILL_FIELD") { chrome.runtime.sendMessage({ type: "MAIN_FILL", field: event.data.field, value: event.data.value }).then((result) => window.postMessage({ source: "bolo-sahayak-extension", ...result }, location.origin)); return; }
  window.postMessage({ source: "bolo-sahayak-extension", ...handle(event.data, "window") }, location.origin);
});
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => { sendResponse(handle(message)); });
