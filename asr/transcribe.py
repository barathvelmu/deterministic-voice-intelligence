import tempfile 
import whisper 

_model = whisper.load_model("base")

def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    """Transcribe a WAV file given as bytes, and return the transcribed text as a string."""
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        f.write(wav_bytes)
        f.flush()
        result = _model.transcribe(f.name, fp16 = False)
        return (result.get("text" or "")).strip()