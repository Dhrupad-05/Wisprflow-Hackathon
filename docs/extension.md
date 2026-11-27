# Bolo Sahayak browser helper

The extension is an MV3 demo helper for the registry allow-list. It fills only non-sensitive fields on `localhost` and `127.0.0.1`; it refuses OTP, PIN, password, CVV, Aadhaar, passcode, password-type, one-time-code, and `data-sensitive` fields by inspecting the DOM itself.

## Install locally

1. Run `python tools/build_extension.py`.
2. Open Chromium extensions and enable Developer mode.
3. Choose **Load unpacked** and select `apps/extension`.
4. Open the Bolo Sahayak app or a local mock portal, then open the extension side panel.

The assistant-to-extension relay uses `window.postMessage` with `source: "bolo-sahayak"`; content scripts validate the page origin and return only operation status. They never read sensitive values.
