from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from openai import OpenAI

SYSTEM_PROMPT = """You rewrite free-form voice transcripts into compact commands for a voice agent.\nReturn a JSON object with keys:\n  action: one of [\"search\", \"calculate\", \"add_note\", \"list_notes\", \"answer\"].\n  content: short string payload (may be empty for list_notes).\nRules:\n- Use action=\"search\" when the user asks to find, learn about, or research something. content should be the topic.\n- Use action=\"calculate\" for math questions. content should contain only the expression (numbers/operators).\n- Use action=\"add_note\" when the user wants to remember something. content is the note text.\n- Use action=\"list_notes\" when they want to hear existing notes.\n- Use action=\"answer\" for everything else. Keep content under 200 characters and conversational.\n- Never include explanations outside the JSON.\nExamples:\nInput: \"I really want to learn about Donald Trump today.\" -> {\"action\": \"search\", \"content\": \"Donald Trump\"}\nInput: \"Could you remind me to call mom tomorrow?\" -> {\"action\": \"add_note\", \"content\": \"call mom tomorrow\"}\nInput: \"How much is fourteen times nine?\" -> {\"action\": \"calculate\", \"content\": \"14 * 9\"}\nInput: \"What notes do I have saved?\" -> {\"action\": \"list_notes\", \"content\": \"\"}\nInput: \"Just wanted to say hi!\" -> {\"action\": \"answer\", \"content\": \"Hi there!\"}\n"""
MODEL_ID = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
_REFERER = os.getenv("OPENROUTER_SITE_URL", "")
_TITLE = os.getenv("OPENROUTER_SITE_TITLE", "")

@dataclass
class NormalizerResult:
    transcript: str
    answer: Optional[str] = None

def _extract_json(text: str) -> Optional[dict]:
    """This function extracts a JSON object from a text string."""
    if not text:
        return None
    # Use regex to find the JSON object
    match = re.search(r"\{.*\}", text, re.S)
    target = match.group(0) if match else text
    try:
        return json.loads(target)
    except Exception:
        return None

@lru_cache(maxsize=1)
def _client() -> Optional[OpenAI]:
    """This function returns an OpenAI client if OPENROUTER_API_KEY is set."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def rewrite_transcript(raw: str) -> NormalizerResult:
    """Sends to LLM to get normalized. So a short answer back."""
    raw = (raw or "").strip()
    client = _client()
    if not raw or client is None:
        return NormalizerResult(raw)

    try:
        resp = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw},
            ],
            max_tokens=200,
            temperature=0.1,
            extra_headers={key: value for key, value in {
                "HTTP-Referer": _REFERER or None,
                "X-Title": _TITLE or None,
            }.items() if value},
        )
        content = resp.choices[0].message.content if resp.choices else ""
    except Exception:
        return NormalizerResult(raw)

    data = _extract_json(content or "")
    if not data:
        return NormalizerResult(raw)

    action = (data.get("action") or "").strip().lower()
    payload = (data.get("content") or "").strip()

    if action == "search":
        topic = payload or raw
        return NormalizerResult(f"search {topic}")
    if action == "calculate":
        expression = payload or raw
        return NormalizerResult(f"calculate {expression}")
    if action == "add_note":
        note = payload or raw
        return NormalizerResult(f"add a note {note}")
    if action == "list_notes":
        return NormalizerResult("list notes")
    if action == "answer" and payload:
        concise = payload[:240].strip()
        return NormalizerResult(raw, answer=concise)

    return NormalizerResult(raw)
