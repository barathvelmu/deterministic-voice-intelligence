import os
from typing import Optional
from urllib.parse import quote_plus
import requests
from dotenv import load_dotenv
from requests.exceptions import RequestException

load_dotenv()

ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "")
ELEVEN_MODEL_ID = os.getenv("ELEVEN_MODEL_ID", "eleven_multilingual_v2")

def is_configured() -> bool:
    """
    Return True when required ElevenLabs env vars are present.
    """
    return bool(ELEVEN_API_KEY and ELEVEN_VOICE_ID)


def _ensure_env() -> None:
    """
    Raise RuntimeError if ElevenLabs config is missing.
    """
    if not is_configured():
        raise RuntimeError("ElevenLabs not configured. Set ELEVEN_API_KEY and ELEVEN_VOICE_ID.")


def _build_url(voice_id: str) -> str:
    """
    Here, I build the URL at call-time so changes to environment during runtime
    (tests or reloading) are respected.
    """
    return f"https://api.elevenlabs.io/v1/text-to-speech/{quote_plus(voice_id)}"

def tts_to_wav_bytes(text: str, timeout: int = 60, retries: int = 1) -> bytes:
    """
    Synthesize `text` to WAV bytes using ElevenLabs.
    Raises RuntimeError for missing config, network errors, or HTTP errors.
    """
    _ensure_env()
    if not text:
        text = "There is no text for me to speak."

    url = _build_url(ELEVEN_VOICE_ID)
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/wav",
    }
    payload = {
        "text": text,
        "model_id": ELEVEN_MODEL_ID,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        "output_format": "wav",
    }

    # Just adding retry logic. 
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            # this is the MAIN FOCUS: 
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except RequestException as exc:
            last_exc = exc
            # simple retry/backoff for transient failures
            if attempt < retries:
                # small backoff
                try:
                    import time
                    time.sleep(0.5 * (attempt + 1))
                except Exception:
                    pass
                continue
            raise RuntimeError(f"Network error contacting ElevenLabs TTS: {exc}") from exc

        if not r.ok:
            # reasonable snippet of the response body
            body_snippet = (r.text or "")[:200]
            raise RuntimeError(f"ElevenLabs TTS error: {r.status_code} {body_snippet}")
        return r.content

    # If we reach here, raise the last exception for visibility
    if last_exc:
        raise RuntimeError(f"ElevenLabs TTS failed after retries: {last_exc}")
    raise RuntimeError("ElevenLabs TTS failed for unknown reasons.")