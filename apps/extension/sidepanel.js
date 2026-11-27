const allowList = ["localhost", "127.0.0.1"];
const render = (state = {}) => { document.querySelector("#status").textContent = state.connected === false ? "Disconnected" : "Connected"; document.querySelector("#portal").textContent = state.currentPortal || "None"; document.querySelector("#allowlist").innerHTML = allowList.map((host) => `<li>${host}</li>`).join(""); const fills = state.lastFills || []; document.querySelector("#fills").innerHTML = fills.length ? fills.map((fill) => `<li>${fill.field} · ${fill.origin}</li>`).join("") : "<li>None</li>"; };
chrome.storage.local.get("state").then(({ state }) => render(state));
chrome.runtime.onMessage.addListener((message) => { if (message.type === "STATE") render(message.state); });
