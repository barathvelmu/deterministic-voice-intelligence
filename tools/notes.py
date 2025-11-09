_NOTES = []

def add_note(text: str):
    """Adds `text` to the list of notes."""
    text = (text or "").strip()
    if text:
        _NOTES.append(text)
    return {"ok": True, "count": len(_NOTES)}

def list_notes():
    """Returns the list of notes."""
    return {"ok": True, "count": len(_NOTES), "notes": list(_NOTES)}
