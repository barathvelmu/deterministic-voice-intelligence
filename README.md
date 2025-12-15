# Deterministic Voice Intelligence

[Project Demo](https://youtu.be/tM1OUXeL1Dw)

[Technical Writeup](https://barathvelmu.medium.com/engineering-deterministic-voice-intelligence-dvi-a-passion-project-b35fb3f646b5)

A tap-to-talk voice assistant that transcribes speech with Whisper, rewrites it with Meta’s Llama 3.3 70B via OpenRouter, routes intent through LangGraph tools (search, calculator, notes), and replies with ElevenLabs TTS.

<img width="1466" height="833" alt="image" src="https://github.com/user-attachments/assets/181e0879-e3f1-4655-aa16-bda40040892f" />

### Architecture

1. **Whisper ASR** – `/asr` accepts WAV uploads, validates them, and transcribes audio with OpenAI Whisper (`asr/transcribe.py`).
2. **LLM Normalizer** – `services/normalizer.py` calls the OpenRouter model (`meta-llama/llama-3.3-70b-instruct:free`) to turn free-form text into commands (`search …`, `calculate …`, `add note …`, etc.). If no tool fits, it emits a short direct answer.
3. **LangGraph Agent** – `agent/graph.py` detects intents, calls tools (`tools/search.py`, `tools/calculator.py`, `tools/notes.py`), and generates conversational replies. `verifier()` trims responses for speech.
4. **ElevenLabs TTS** – `/tts` streams WAV bytes from `tts/synth.py`, and the UI auto-plays the reply (tap again to stop).

### Prerequisites

- Python 3.12+
- ElevenLabs API credentials: `ELEVEN_API_KEY`, `ELEVEN_VOICE_ID`.
- OpenRouter API key: `OPENROUTER_API_KEY`) for the Llama normalizer.

Put these in `.env` (which lives in project root) and the backend will read them via `python-dotenv`.

### .env File
```bash
ELEVEN_API_KEY=something
ELEVEN_VOICE_ID=something
OPENROUTER_API_KEY=something
```

### Backend Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8010
```

### Web UI

Open `http://127.0.0.1:8010/ui/` and tap the mic. 

### Testing
Run `pytest -v` to run all tests.

### How to Talk to It

- “Search for MIT" → summarized Wikipedia snippet.
- “How about nine times ten?” → calculator result.
- “Add a note remind me to call mom tomorrow” → note saved.
- “What notes do I have?” → lists your in-memory notes.
- "I did mental math to solve 158 + 56, what is the answer?" → calculator result (more complex query) .

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
