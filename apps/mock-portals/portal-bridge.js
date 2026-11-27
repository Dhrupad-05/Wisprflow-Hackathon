(function installPortalBridge() {
  "use strict";

  function allowed(event) {
    // The parent is the only trusted sender; the old event.source === window check was incorrect inside an iframe.
    return event.origin === window.location.origin && event.source === window.parent;
  }

  function fieldFor(id) {
    return document.querySelector(`[data-field="${CSS.escape(id)}"]`);
  }

  window.addEventListener("message", (event) => {
    if (!allowed(event) || !event.data || typeof event.data.type !== "string") {
      return;
    }
    const message = event.data;
    if (message.type === "PING") {
      event.source.postMessage({ type: "PONG" }, event.origin);
      return;
    }
    const field = fieldFor(message.field);
    if (!field || field.getAttribute("data-sensitive") === "true") {
      event.source.postMessage({ type: "REFUSED", reason: "unknown-or-sensitive-field" }, event.origin);
      return;
    }
    if (message.type === "FILL_FIELD") {
      field.value = String(message.value ?? "");
      field.dispatchEvent(new Event("input", { bubbles: true }));
      field.dispatchEvent(new Event("change", { bubbles: true }));
      event.source.postMessage({ type: "FILLED", field: message.field }, event.origin);
    }
    if (message.type === "HIGHLIGHT") {
      field.focus();
      field.style.outline = "4px solid #f59e0b";
    }
  });
})();
