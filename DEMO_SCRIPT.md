# Three-minute demo

Voice needs no provider key: the server runs `faster-whisper` locally on the CPU. The first start downloads the `small` model (~500 MB); wait for the chip to leave “Voice engine loading…” and `/v1/health` to show `"whisper_local":"ready"` before going on stage.

1. Open `http://127.0.0.1:8000`, point out the green **Voice ready: Local voice** chip and the consent notice: mock portals only, OTP/PIN/password typed by the user, nothing submitted without an explicit yes.
2. Press the mic and say **“SBI mein paanch hazaar jama karna hai”**. The level meter moves, the live transcript appears, and “What I heard” shows the transcript. Expect about 2.5 seconds on this laptop.
3. Type `Ami chashi, amar loan lagbe`, choose `SBI`, then change your mind with `Na, taka jama dite chai`. (Typed input is still the fastest path if the room is noisy.)
4. Enter `one two three four five six seven eight nine zero one`, correct it once with **Fix the number** or by dictating the digits again, enter `paanch hazaar`, and confirm with `haan`. Open **Voice diagnostics** and show `whisper_local`, the error list, and the latency for the last turn — then copy it if someone asks for the numbers.
5. At the OTP step, type `123456` directly into the demo portal and select `I'm done`; the assistant never receives or stores it. Enable private mode, open the masked log, and repeat that this is a mock portal, not a real bank.

## If voice does not transcribe

- **“I could not hear speech, please try again.”** The local engine ran and heard silence. Check the mic device in the dropdown, run **Mic test**, and speak closer. The app deliberately retries the same microphone instead of opening a second recognizer.
- **Chip says “Voice engine loading…”** The model is still warming up; wait for the poll to turn it green, or pre-warm by opening `/v1/health`.
- **No mic at all** Use the typed box; every step of the demo works without voice.
- **A red banner** Read it once, dismiss it, and open **Voice diagnostics**: browser, secure context, device, peak level, server engines, and the last STT response are all listed there.
