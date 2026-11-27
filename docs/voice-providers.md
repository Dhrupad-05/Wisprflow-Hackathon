# Voice provider setup

The browser never receives provider credentials. Set these variables in `.env` on the server:

```powershell
XAI_STT_API_KEY=<xAI key for speech-to-text>
XAI_TTS_API_KEY=<xAI key for text-to-speech>
GEMINI_API_KEY=<primary routing key>
XAI_LLM_API_KEY=<alternate Grok-compatible routing key>
OPENROUTER_API_KEY=<fallback routing key>
XAI_FALLBACK_API_KEY=<last-resort Grok-compatible routing key>
```

The pipeline is:

`microphone → WAV → POST /v1/stt → xAI grok-voice-transcribe-2.0 → /v1/turn → POST /v1/tts → xAI audio`

When a provider key is absent, the app remains usable with typed input and browser speech synthesis. Provider failures are returned as safe status codes; raw keys and audio are not logged or persisted.

Because credentials were pasted into a chat, rotate them in the provider consoles if they are real production keys, then place only replacement values in the local ignored `.env` file.
