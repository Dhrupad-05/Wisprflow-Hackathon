/* Visible-field scanner. Sends only a schema: never values. */
globalThis.BOLO_SCAN = function boloScan(rootDocument = document) {
  const SENSITIVE = /otp|pin|password|cvv|cvc|aadhaar|aadhar|passcode|card number|card no/i;
  const fields = [];
  const visit = (doc, frame) => {
    const elements = doc.querySelectorAll("input, select, textarea");
    elements.forEach((field) => {
      if (!field.offsetParent && field.type !== "hidden") return;
      if (["hidden", "submit", "button", "reset", "file", "image", "checkbox", "radio"].includes(field.type)) return;
      if (field.disabled || field.readOnly) return;
      const labels = field.labels ? [...field.labels].map((label) => label.textContent) : [];
      const label = (field.getAttribute("aria-label") || labels.join(" ") || field.placeholder || field.name || field.id || "").trim().slice(0, 120);
      const metadata = [field.type, field.name, field.id, field.getAttribute("aria-label"), label, field.getAttribute("autocomplete")].join(" ");
      const sensitive = field.getAttribute("data-sensitive") === "true" || field.type === "password" || SENSITIVE.test(metadata);
      fields.push({
        id: field.getAttribute("data-field") || field.name || field.id || "",
        label,
        type: field.tagName === "SELECT" ? "select" : field.type || "text",
        options: field.tagName === "SELECT" ? [...field.options].map((option) => option.textContent.trim()).slice(0, 20) : [],
        sensitive,
        required: field.required,
        frame: frame || null,
        readOnly: sensitive,
      });
    });
  };
  visit(rootDocument, null);
  rootDocument.querySelectorAll("iframe").forEach((frame) => {
    try {
      if (frame.contentDocument) visit(frame.contentDocument, frame.getAttribute("src") || "about:blank");
    } catch {
      // Cross-origin frames are never inspected.
    }
  });
  return fields;
};
