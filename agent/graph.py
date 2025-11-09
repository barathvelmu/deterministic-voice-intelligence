from __future__ import annotations
import re
from typing import Any, Dict, TypedDict
from langgraph.graph import END, StateGraph
from tools.calculator import calc
from tools.notes import add_note, list_notes
from tools.search import wiki_summary

class State(TypedDict, total=False):
    transcript: str
    intent: str
    tool_result: Any
    draft_answer: str
    answer: str
    calc_status: int
    truncated: bool
    full_answer: str
    continuation: str

# Maximum length for spoken answer (voice-friendly). Short, so TTS replies are snappy! 
SPOKEN_MAX_LEN = 300

def _normalize(text: str) -> str:
    """Normalize transcript for processing."""
    # lower-case, strip, and collapse whitespace
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def router(state: State) -> Dict[str, Any]:
    """
    Decide next node based on transcript | NOTES > CALC > SEARCH > ANSWER.
    """
    t = _normalize(state.get("transcript", ""))
    updates: Dict[str, Any] = {}

    # quick early return for empty transcript
    if not t:
        updates["intent"] = "ANSWER"
        return updates

    # detect simple negation near intent keywords
    negation = bool(re.search(r"\b(don't|do not|do n't|never|no)\b", t))

    if re.search(r"\b(add note|add a note|take a note|remember to|note to|note:|remind me to)\b", t) and not negation:
        updates["intent"] = "NOTES"
        return updates
    if re.search(r"\b(list notes|show notes|read notes|what notes|my notes)\b", t) and not negation:
        updates["intent"] = "NOTES_LIST"
        return updates

    # CALC intent: arithmetic operators or calculate keywords
    if (re.search(r"\b(calculate|what is|what's|how much is|evaluate|what about|how about)\b", t)
            or re.search(r"\b\d+\b", t) and re.search(r"[+\-*/%]|\*\*", t)) and not negation:
        updates["intent"] = "CALC"
        return updates

    # SEARCH intent: match words like search, find, look up, lookup, look for
    if re.search(r"\b(search|search for|find|look up|lookup|look for|tell me about)\b", t) and not negation:
        updates["intent"] = "SEARCH"
        return updates

    # fallback
    updates["intent"] = "ANSWER"
    return updates


def tool_node(state: State) -> State:
    """This function calls the appropriate tool."""
    intent = state.get("intent")
    t = _normalize(state.get("transcript", ""))
    updates: State = {"tool_result": []}
    
    # Use if else to call the right tools
    if intent == "SEARCH":
        q = re.sub(r"\b(search for|search|look up|lookup|find|look for)\b", "", t, count=1)
        q = re.sub(r"^\b(please|for|to)\b\s*", "", q)
        q = re.sub(r"\s+", " ", q).strip()
        updates["tool_result"] = wiki_summary(q) if q else []
    elif intent == "NOTES":
        payload = re.sub(r"\b(add a note|add note|take a note|remember to|note to|note:|remind me to)\b", "", t, count=1)
        payload = re.sub(r"\s+", " ", payload).strip()
        updates["tool_result"] = add_note(payload) if payload else {"ok": False, "count": 0}
    elif intent == "NOTES_LIST":
        updates["tool_result"] = list_notes()
    elif intent == "CALC":
        expression = re.sub(r"\b(calculate|what is|what's|how much is|evaluate|what about|how about)\b", "", t, count=1)
        expression = re.sub(r"[?]+$", "", expression)
        expression = re.sub(r"\s+", " ", expression).strip() or t
        res, code = calc(expression)
        updates["tool_result"] = res
        updates["calc_status"] = code

    return updates


def answerer(state: State) -> State:
    """The focus of this function is to produce a voice-friendly answer."""
    intent = state.get("intent")
    updates: State = {}
    
    # This part focuses on the search (task type 1)
    if intent == "SEARCH":
        snippets = state.get("tool_result") or []
        if not snippets:
            updates["draft_answer"] = "I couldn’t find anything solid on that topic. Try rephrasing it for me."
        else:
            lines = []
            for s in snippets[:2]:
                title = s.get("title", "(no title)")
                summary = (s.get("summary") or "").replace("\n", " ")
                if len(summary) > 400:
                    summary = summary[:397].rstrip() + "..."
                lines.append(f"{title}: {summary}")
            updates["draft_answer"] = "Here’s what I found.\n" + "\n".join(lines)
    
    # This part focuses on notes (task type 2)
    elif intent == "NOTES":
        result = state.get("tool_result") or {}
        if result.get("ok"):
            count = result.get("count", 0)
            plural = "note" if count == 1 else "notes"
            updates["draft_answer"] = f"Got it. I’ll remember that. You now have {count} {plural}."
        else:
            updates["draft_answer"] = "I couldn’t save that note. Please try again."
    elif intent == "NOTES_LIST":
        result = state.get("tool_result") or {}
        notes = result.get("notes") or []
        count = result.get("count", len(notes))
        if not notes:
            updates["draft_answer"] = "You don’t have any notes yet. Just ask me to remember something."
        else:
            lines = []
            for idx, text in enumerate(notes[:5], start=1):
                lines.append(f"Note {idx}: {text}.")
            remaining = count - len(lines)
            tail = f" I’m tracking {remaining} more." if remaining > 0 else ""
            updates["draft_answer"] = "Here’s what you asked me to remember. " + " ".join(lines) + tail
    
    # This part focuses on calculations (task type 3)            
    elif intent == "CALC":
        tr = state.get("tool_result") or {}
        code = state.get("calc_status")
        if code == 200 and "result" in tr:
            updates["draft_answer"] = f"The answer is {tr['result']}."
        else:
            err = tr.get("error") or "invalid expression or unsupported characters"
            updates["draft_answer"] = f"I couldn’t work that out because {err}."
    else:
        raw = state.get("transcript", "") or ""
        clean = raw.strip()
        updates["draft_answer"] = f"You said “{clean}.”" if clean else "I didn’t catch that."

    return updates


def verifier(state: State) -> State:
    """
    Voice-friendly answer chunk and keep the remainder for continuation.
    - Normalize missing answers to empty string and trim whitespace.
    - If the answer fits within SPOKEN_MAX_LEN, return it as-is and mark not truncated.
    - If longer, cut at the last sentence-ending punctuation within the limit.
      If none, cut at the last space. 
    - Store the full answer and the remainder so the voice layer can ask to continue or stream
      the rest on demand.
    """
    ans = (state.get("draft_answer") or state.get("answer") or "").strip()
    updates: State = {"truncated": False, "continuation": "", "full_answer": None}

    if not ans:
        updates["answer"] = ""
        return updates

    if len(ans) <= SPOKEN_MAX_LEN:
        updates["answer"] = ans
        return updates

    # Try to cut at a sentence boundary within the spoken limit
    cut = ans.rfind('.', 0, SPOKEN_MAX_LEN)
    if cut == -1:
        cut = ans.rfind('!', 0, SPOKEN_MAX_LEN)
    if cut == -1:
        cut = ans.rfind('?', 0, SPOKEN_MAX_LEN)
    if cut != -1 and cut > 0:
        spoken = ans[: cut + 1].strip()
    else:
        # fall back to last space inside the limit
        space_cut = ans.rfind(' ', 0, SPOKEN_MAX_LEN)
        if space_cut != -1 and space_cut > 0:
            spoken = ans[: space_cut].strip()
        else:
            # last resort: hard cut at the spoken max length
            spoken = ans[: SPOKEN_MAX_LEN].rstrip()

    remainder = ans[len(spoken):].lstrip()

    updates["full_answer"] = ans
    updates["answer"] = spoken
    updates["continuation"] = remainder
    updates["truncated"] = True
    return updates

# Lang-graph Tie Up 
def build_graph():
    """Here, we tie up the pieces of the graph together."""
    g = StateGraph(State)
    g.add_node("detect_intent", router)
    g.add_node("dispatch_tool", tool_node)
    g.add_node("compose_answer", answerer)
    g.add_node("verify_answer", verifier)
    g.set_entry_point("detect_intent")
    g.add_edge("detect_intent", "dispatch_tool")
    g.add_edge("detect_intent", "compose_answer")
    g.add_edge("dispatch_tool", "compose_answer")
    g.add_edge("compose_answer", "verify_answer")
    g.add_edge("verify_answer", END)
    return g.compile() 
