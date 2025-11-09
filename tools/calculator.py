from __future__ import annotations
import math
import re

_ALLOWED = set("0123456789+-*/(). %")

_WORD_OPERATORS = [
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"\bover\b", "/"),
    (r"\bdivided by\b", "/"),
    (r"\bdivide by\b", "/"),
    (r"\btimes\b", "*"),
    (r"\bmultiplied by\b", "*"),
    (r"\bmultiply by\b", "*"),
    (r"\bmodulo\b", "%"),
    (r"\bmod\b", "%"),
    (r"\bpower of\b", "**"),
    (r"\bto the power of\b", "**"),
    (r"\braised to\b", "**"),
]

_NUM_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_SCALE_WORDS = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}
_IGNORE_WORDS = {"and"}
_ALL_NUMBER_WORDS = set(_NUM_WORDS) | set(_SCALE_WORDS) | _IGNORE_WORDS

def _words_sequence_to_int(words: list[str]) -> int | None:
    """Here, we convert a sequence of words to an integer."""
    total = 0
    current = 0
    for word in words:
        if word in _IGNORE_WORDS:
            continue
        if word in _NUM_WORDS:
            current += _NUM_WORDS[word]
        elif word in _SCALE_WORDS:
            scale = _SCALE_WORDS[word]
            if current == 0:
                current = 1
            current *= scale
            if scale >= 1000:
                total += current
                current = 0
        else:
            return None
    return total + current

def _convert_number_words(expr: str) -> str:
    """This function converts words to numbers."""
    words = expr.split()
    result: list[str] = []
    seq: list[str] = []
    for word in words:
        if word in _ALL_NUMBER_WORDS:
            seq.append(word)
            continue
        if seq:
            number = _words_sequence_to_int(seq)
            if number is not None:
                result.append(str(number))
            else:
                result.extend(seq)
            seq = []
        result.append(word)
    if seq:
        number = _words_sequence_to_int(seq)
        if number is not None:
            result.append(str(number))
        else:
            result.extend(seq)
    return " ".join(result)

def _replace_word_operators(expr: str) -> str:
    """Here, we replace word operators with symbols."""
    normalized = expr.lower()
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[?!,.']", "", normalized)
    normalized = _convert_number_words(normalized)
    for pattern, symbol in _WORD_OPERATORS:
        normalized = re.sub(pattern, f" {symbol} ", normalized)
    normalized = re.sub(r"[a-z]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()

def calc(expression: str):
    """This function evaluates a math expression."""
    expression = _replace_word_operators((expression or "").strip())
    if not expression or not set(expression).issubset(_ALLOWED):
        return {"error": "invalid characters"}, 400
    try:
        res = eval(expression, {"__builtins__": None}, {"math": math})
        return {"result": res}, 200
    except Exception as exc:
        return {"error": str(exc)}, 400
