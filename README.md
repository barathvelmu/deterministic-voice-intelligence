## Voice Agent

A tap-to-talk voice assistant that transcribes speech with Whisper, rewrites it with Meta’s Llama 3.3 70B via OpenRouter, routes the intent through LangGraph tools (search, calculator, notes), and replies with ElevenLabs TTS.

### Architecture

1. **Whisper ASR** – `/asr` accepts WAV uploads, validates them, and transcribes audio with OpenAI Whisper (`asr/transcribe.py`).
2. **LLM Normalizer** – `services/normalizer.py` calls the OpenRouter model (`meta-llama/llama-3.3-70b-instruct:free`) to turn rambly transcripts into canonical commands (`search …`, `calculate …`, `add note …`, etc.). If no tool fits, it emits a short direct answer.
3. **LangGraph Agent** – `agent/graph.py` detects intents, calls tools (`tools/search.py`, `tools/calculator.py`, `tools/notes.py`), and generates conversational replies. `verifier()` trims responses for speech.
4. **ElevenLabs TTS** – `/tts` streams WAV bytes from `tts/synth.py`, and the UI auto-plays the reply (tap again to stop).

### Prerequisites

- Python 3.12+
- ElevenLabs API credentials (`ELEVEN_API_KEY`, `ELEVEN_VOICE_ID`, optionally `ELEVEN_MODEL_ID`).
- OpenRouter API key (`OPENROUTER_API_KEY`) for the Llama normalizer. Optional env vars: `OPENROUTER_MODEL`, `OPENROUTER_SITE_URL`, `OPENROUTER_SITE_TITLE`.

Put these in `.env` and the backend will read them via `python-dotenv`.

### Backend Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8010
```

### Web UI

Open `http://127.0.0.1:8010/ui/` and tap the mic. The HTML/CSS/JS live in `ui/static/`.

### Testing
Run `pytest -v` to run all tests.

### How to Talk to It

- “Search for MIT" → summarized Wikipedia snippet.
- “How about nine times ten?” → calculator result.
- “Add a note remind me to call mom tomorrow” → note saved.
- “What notes do I have?” → lists your in-memory notes.
- Ramble about anything else → Llama rewrites it or answers directly in one line.

### Repo Layout

```
api/
  main.py              # FastAPI entrypoint
asr/transcribe.py      # Whisper helper
services/normalizer.py # OpenRouter LLM rewrites
agent/graph.py         # LangGraph state machine
tools/*.py             # Search, calculator, notes
tts/synth.py           # ElevenLabs client
ui/static/             # Minimal tap-to-talk frontend
```

### Notes

- Notes are in-memory; restart clears them.
- The frontend auto-stops TTS playback if you tap the mic mid-response.
- The LLM layer is optional: if `OPENROUTER_API_KEY` is missing, transcripts bypass the normalizer.
