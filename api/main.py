from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from agent.graph import build_graph, verifier
from asr.transcribe import transcribe_wav_bytes
from tts.synth import tts_to_wav_bytes
from services.normalizer import rewrite_transcript

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "ui" / "static"

app = FastAPI(title="Voice Agent")
graph = build_graph()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

if STATIC_DIR.exists():
    app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")

# 10 MB cap keeps ASR predictable
MAX_WAV_BYTES = 10 * 1024 * 1024

class AgentPayload(BaseModel):
    """Schema for `/agent` requests so transcripts stay bounded."""
    transcript: str = Field(default="", max_length=4000)

class TTSPayload(BaseModel):
    """Schema for `/tts` requests to control text length."""
    text: str = Field(default="", max_length=4000)

# HELPER CODES TO CATCH + HANDLE FAILURES: 
def _validate_wav_upload(file: UploadFile, wav_bytes: bytes) -> None:
    """Reject missing, oversized, or non-WAV uploads before Whisper sees them."""
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail = "No file uploaded.")
    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=415, detail = "Only .wav files are supported.")
    if not wav_bytes:
        raise HTTPException(status_code=400, detail = "The uploaded file is empty.")
    if len(wav_bytes) > MAX_WAV_BYTES:
        raise HTTPException(status_code=413, detail = "Audio file is too large (max 10 MB).")
    if not (wav_bytes.startswith(b"RIFF") and wav_bytes[8:12] == b"WAVE"):
        raise HTTPException(status_code=422, detail = "File content is not a valid WAV stream.")

def _transcribe_or_error(wav_bytes: bytes) -> str:
    """Run Whisper transcription and map common failures onto HTTP errors."""
    try:
        return transcribe_wav_bytes(wav_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail= f"Unable to transcribe audio: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail= f"ASR service unavailable: {exc}") from exc
    except Exception as exc: 
        raise HTTPException(status_code=500, detail= "Unexpected ASR failure") from exc

def _invoke_agent(transcript: str):
    """Delegate to LangGraph and keep transport-level errors consistent."""
    try:
        return graph.invoke({"transcript": transcript})
    except Exception as exc:  
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

def _tts_or_error(text: str) -> bytes:
    """Call ElevenLabs TTS and surface clean HTTP errors."""
    try:
        return tts_to_wav_bytes(text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"TTS service unavailable: {exc}") from exc
    except Exception as exc:  
        raise HTTPException(status_code=500, detail="Unexpected TTS failure") from exc

# =====================================================================

# MAIN FOCUS CODE: 
# Whisper 
@app.get("/")
async def root():
    """Serve UI, otherwise expose a health payload."""
    if STATIC_DIR.exists():
        return RedirectResponse(url="/ui/")
    return {"status": "ok"}

@app.post("/asr")
async def asr_endpoint(file: UploadFile):
    """Accept a WAV upload, run Whisper ASR, and return the transcript."""
    wav = await file.read()
    _validate_wav_upload(file, wav)
    text = _transcribe_or_error(wav)
    return {"transcript": text}

# Lang-Graph
@app.post("/agent")
async def agent_endpoint(payload: AgentPayload):
    """Send transcript to LangGraph for processing."""
    transcript = (payload.transcript or "").strip()
    normalized = rewrite_transcript(transcript)

    if normalized.answer:
        verified = verifier({"draft_answer": normalized.answer})
        return {
            "text": verified.get("answer", normalized.answer),
            "intent": "ANSWER",
            "tool_result": None,
        }

    cleaned = (normalized.transcript or transcript).strip() or transcript
    state = _invoke_agent(cleaned)
    return {
        "text": state.get("answer", ""),
        "intent": state.get("intent", "ANSWER"),
        "tool_result": state.get("tool_result", None)
    }

# ElevenLabs
@app.post("/tts")
async def tts_endpoint(payload: TTSPayload):
    """Send the text to ElevenLabs and stream the returned WAV payload."""
    text = (payload.text or "").strip()
    audio_bytes = _tts_or_error(text)
    return StreamingResponse(iter([audio_bytes]), media_type="audio/wav")
