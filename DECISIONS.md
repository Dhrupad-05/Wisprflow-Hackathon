# Decisions

- 2026-11-27: Use FastAPI plus a static browser client because the workspace had no starter code and this keeps demo startup reliable without a Node install.
- 2026-11-27: Treat the documented mock portals as the only submission targets; real banking and government automation is out of scope for safety.
- 2026-11-27: Use deterministic keyword routing when LLM credentials are absent; it preserves the safety gate and makes tests reproducible.
- 2026-11-27: Keep amounts as safe session data but mask them in activity logs; this follows the architecture's masked-log requirement.
- 2026-11-27: Browser SpeechSynthesis is the default TTS because it requires no secret and works offline; missing Indic voices are surfaced in the UI.
- 2026-11-27: The original Wispr intake was removed after the provider became unavailable; xAI STT/TTS are now the server-side voice pipeline, with browser speech as a fallback.
- 2026-11-27: Phase 0 fixed decisions intentionally keep one FastAPI process and a plain ES-module client; this deviates from the TRD React/Vite suggestion so a clean machine needs Python only.
- 2026-11-27: Phase 8 uses strict same-origin behavior instead of permissive CORS, with an environment-configurable rate limit and CSP headers applied by middleware.
- 2026-11-27: Phase 9 proceeds at the user's request while Phase 8's axe-core and throttled-CDP checks remain explicitly listed as not verified live.
