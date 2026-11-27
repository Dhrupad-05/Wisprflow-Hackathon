import { recordWav } from "./mic.js";

const allowList = globalThis.ALLOWED_HOSTS || ["localhost", "127.0.0.1"];
const $ = (id) => document.getElementById(id);
let stored = { apiBase: "http://127.0.0.1:8000", lang: "en" };

const render = (state = {}) => {
  stored = { ...stored, ...state };
  $("conn").textContent = state.connected === false ? "Disconnected" : "Connected";
  $("portal").textContent = state.currentPortal || "None";
  $("fields").textContent = String((state.pageFields || []).length);
  $("allowlist").innerHTML = allowList.map((host) => `<li>${host}</li>`).join("");
  const fills = state.lastFills || [];
  $("fills").innerHTML = fills.length ? fills.map((fill) => `<li>${fill.field} · ${fill.origin}</li>`).join("") : "<li>None</li>";
};

const renderBolo = (state = {}) => {
  if (state.prompt) $("prompt").textContent = state.prompt;
  if (state.transcript) $("heard").textContent = `“${state.transcript}”`;
  $("status").textContent = state.error || state.status || "Idle";
  if (state.fields) $("fields").textContent = String(state.fields.length);
};

chrome.storage.local.get("state").then(({ state }) => render(state));
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "STATE") render(message.state);
  if (message.type === "BOLO_STATE") renderBolo(message.state);
});

const send = (type, extra = {}) => chrome.runtime.sendMessage({ type, ...extra }).catch(() => {
  $("status").textContent = "Extension is reloading. Reopen the panel.";
});

$("yes").addEventListener("click", () => send("BOLO_TEXT", { text: "yes" }));
$("no").addEventListener("click", () => send("BOLO_TEXT", { text: "no" }));
$("send").addEventListener("click", () => {
  const text = $("typed").value.trim();
  if (!text) return;
  $("typed").value = "";
  send("BOLO_TEXT", { text });
});
$("typed").addEventListener("keydown", (event) => { if (event.key === "Enter") $("send").click(); });

$("ask").addEventListener("click", async () => {
  if (!navigator.mediaDevices?.getUserMedia) {
    $("status").textContent = "This browser cannot record audio.";
    return;
  }
  $("ask").disabled = true;
  $("status").textContent = "Listening for 6 seconds…";
  try {
    const wav = await recordWav(6000);
    $("status").textContent = "Transcribing…";
    const bytes = new Uint8Array(wav);
    let binary = "";
    bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
    const response = await fetch(stored.apiBase.replace(/\/$/, "") + "/v1/stt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio: btoa(binary), language: stored.lang }),
    }).then((result) => result.json());
    if (response.text) {
      $("status").textContent = "Thinking…";
      send("BOLO_TEXT", { text: response.text });
    } else {
      $("status").textContent = "I did not hear words. Try again or type below.";
    }
  } catch (error) {
    $("status").textContent = error?.name === "NotAllowedError" ? "Allow microphone access for this extension." : "Microphone could not start.";
  } finally {
    $("ask").disabled = false;
  }
});
