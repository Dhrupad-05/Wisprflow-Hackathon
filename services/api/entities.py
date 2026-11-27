"""Pure language, entity, and privacy helpers for the assistant."""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANKS = json.loads(
    (ROOT / "packages/registries/banks.json").read_text(encoding="utf-8")
)
SCHEMES = json.loads(
    (ROOT / "packages/registries/schemes.json").read_text(encoding="utf-8")
)

DIGITS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "shunya": "0",
    "ek": "1",
    "do": "2",
    "teen": "3",
    "tin": "3",
    "char": "4",
    "chaar": "4",
    "paanch": "5",
    "panch": "5",
    "pach": "5",
    "chhe": "6",
    "che": "6",
    "saat": "7",
    "aath": "8",
    "at": "8",
    "nau": "9",
    "noy": "9",
    "শূন্য": "0",
    "এক": "1",
    "দুই": "2",
    "দুুই": "2",
    "তিন": "3",
    "চার": "4",
    "পাঁচ": "5",
    "ছয়": "6",
    "ছয়": "6",
    "সাত": "7",
    "আট": "8",
    "নয়": "9",
    "নয়": "9",
    "शून्य": "0",
    "एक": "1",
    "दो": "2",
    "तीन": "3",
    "चार": "4",
    "पाँच": "5",
    "पांच": "5",
    "छह": "6",
    "छः": "6",
    "सात": "7",
    "आठ": "8",
    "नौ": "9",
}

NUMBER_WORDS = {
    **{word: int(value) for word, value in DIGITS.items()},
    "ten": 10,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "das": 10,
    "gyarah": 11,
    "barah": 12,
    "terah": 13,
    "chaudah": 14,
    "pandrah": 15,
    "solah": 16,
    "satrah": 17,
    "atharah": 18,
    "unnis": 19,
    "pachas": 50,
    "pachaas": 50,
    "sau": 100,
    "shat": 100,
    "hundred": 100,
    "hajar": 1000,
    "hazar": 1000,
    "hazaar": 1000,
    "thousand": 1000,
    "হাজার": 1000,
    "হাজ়ার": 1000,
    "শত": 100,
    "লাখ": 100000,
    "लाख": 100000,
    "हज़ार": 1000,
    "हजार": 1000,
    "सौ": 100,
    "lakh": 100000,
    "lakhs": 100000,
    "crore": 10000000,
    "crores": 10000000,
    "eleven": 11,
    "twelve": 12,
    "পাঁচশো": 500,
    "তিনশো": 300,
    "দুইশো": 200,
}

COMMANDS = {
    "yes": {"yes", "yeah", "yep", "haan", "han", "হ্যাঁ", "হ্যা", "हाँ", "हां"},
    "no": {"no", "nahi", "nahin", "না", "নাহি", "नहीं", "नही"},
    "cancel": {"cancel", "रद्द", "বাতিল", "rok do", "band karo"},
    "back": {"back", "पीछे", "পিছনে", "wapas", "ফিরে"},
    "repeat": {"repeat", "फिर बोलिए", "আবার", "dobara"},
    "pause": {"pause", "रुकिए", "থামুন", "rukna"},
    "help": {"help", "मदद", "সাহায্য", "madad"},
    "forget": {"forget everything", "सब भूल जाओ", "সব ভুলে যাও", "bhool jao"},
}

LANGUAGE_WORDS = {
    "bn": {"ami", "amar", "chashi", "chai", "lagbe", "taka", "joma", "করতে", "চাই"},
    "hi": {"mujhe", "mera", "meri", "chahiye", "kisan", "jama", "karna", "hai"},
    "en": {"i", "need", "want", "please", "money", "help", "account"},
}


def _repair(text: str) -> str:
    """Repair the common UTF-8-as-Latin-1 display corruption in old fixtures."""
    if any(marker in text for marker in ("à", "¤", "¦", "§")):
        try:
            return text.encode("latin1").decode("utf-8")
        except UnicodeError:
            pass
    return text


def _normal(text: str) -> str:
    text = _repair(unicodedata.normalize("NFKC", text)).lower()
    return re.sub(r"[^\w\s.\-\u0900-\u097f\u0980-\u09ff]", " ", text)


def detect_language(text: str, hint: str | None = None) -> str:
    """Detect Indic script first, then score Romanized vocabulary."""
    text = _repair(text)
    if re.search(r"[\u0980-\u09ff]", text):
        return "bn"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    tokens = set(_normal(text).split())
    scores = {lang: len(tokens & words) for lang, words in LANGUAGE_WORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return hint if hint in {"en", "hi", "bn"} else "en"


def parse_digits(text: str, expected_length: int | None = None) -> str:
    """Parse spoken single digits without turning ``das`` or ``ten`` into 10."""
    normalized = _normal(text)
    normalized = normalized.replace("double nine", "9 9")
    normalized = normalized.replace("double 9", "9 9")
    normalized = normalized.replace("triple five", "5 5 5")
    normalized = normalized.replace("double", " ").replace("triple", " ")
    result: list[str] = []
    for token in normalized.split():
        if token.isdigit():
            result.extend(token)
        elif token in DIGITS:
            result.append(DIGITS[token])
    value = "".join(result)
    if expected_length is not None and len(value) != expected_length:
        raise ValueError(f"expected {expected_length} digits, got {len(value)}")
    return value


def _word_value(token: str) -> int | float | None:
    return NUMBER_WORDS.get(token)


def parse_amount(text: str) -> float | None:
    """Parse amounts in digits, English, Romanized Hindi/Bengali, or native script."""
    raw = _repair(unicodedata.normalize("NFKC", text)).lower()
    raw = re.sub(r"[₹$€£]", " ", raw)
    scaled = re.search(
        r"(\d+(?:\.\d+)?)\s*(k|hajar|hazar|hazaar|thousand|lakh|হাজার|हजार|हज़ार|लाख|লাখ)",
        raw,
    )
    if scaled:
        multiplier = 100000 if scaled.group(2) in {"lakh", "लाख", "লাখ"} else 1000
        return float(scaled.group(1)) * multiplier
    normalized = _normal(raw).replace("rs", " ")
    compact = normalized.replace(" ", "")
    match = re.search(r"(\d+(?:\.\d+)?)k\b", compact)
    if match:
        return float(match.group(1)) * 1000
    match = re.search(r"\d[\d,.]*(?:\.\d+)?", raw)
    if match and not re.search(r"[a-zA-Z]{2,}", raw.replace("k", "")):
        return float(match.group().replace(",", ""))
    tokens = normalized.split()
    if not tokens:
        return None
    total = 0.0
    current = 0.0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"dhai", "ढाई", "আড়াই", "আড়াই"}:
            current += 2.5
            index += 1
            continue
        if token in {"derh", "dedh", "डेढ़", "দেড়", "দেড়"}:
            current += 1.5
            index += 1
            continue
        if token in {"sade", "sadhe", "साढ़े", "সাড়ে", "সাড়ে"}:
            if index + 1 < len(tokens):
                next_value = _word_value(tokens[index + 1])
                if next_value is not None:
                    current += next_value + 0.5
                    index += 2
                    continue
        value = _word_value(token)
        if value is None:
            index += 1
            continue
        if value == 100:
            current = max(current, 1) * 100
        elif value in {1000, 100000, 10000000}:
            total += max(current, 1) * value
            current = 0
        else:
            current += value
        index += 1
    result = total + current
    return result or None


def _similar(value: str, candidate: str) -> float:
    return difflib.SequenceMatcher(None, _normal(value), _normal(candidate)).ratio()


def resolve_bank(text: str) -> dict | None:
    if re.search(r"\b(any|koi bhi|कोई भी|যে কোনও|যেকোনো)\b", _normal(text)):
        return None
    candidates = []
    for bank in BANKS:
        names = [bank["name"], *bank.get("aliases", [])]
        score = max((_similar(text, name) for name in names), default=0)
        if any(_normal(name) in _normal(text) for name in names):
            score = 1.0
        candidates.append((score, bank))
    score, bank = max(candidates, key=lambda item: item[0])
    return bank if score >= 0.62 else None


def resolve_scheme(text: str) -> dict | None:
    score, result = 0.0, None
    for scheme in SCHEMES:
        for alias in [scheme["name"], *scheme.get("aliases", [])]:
            candidate = (
                1.0 if _normal(alias) in _normal(text) else _similar(text, alias)
            )
            if candidate > score:
                score, result = candidate, scheme
    return result if score >= 0.62 else None


def match_command(text: str) -> str | None:
    normalized = _normal(text)
    for command, words in COMMANDS.items():
        for word in words:
            pattern = rf"(?<!\w){re.escape(_normal(word))}(?!\w)"
            if re.search(pattern, normalized):
                return command
    return None


SENSITIVE = re.compile(
    r"(?i)(?:otp|pin|password|passwd|cvv|aadhaar|aadhar)\s*[:#-]?\s*[^\s,;]{3,}|\b\d{12}\b"
)
ACCOUNT = re.compile(r"\b\d{9,18}\b")


def redact(value: str) -> str:
    value = SENSITIVE.sub("[REDACTED]", value)
    return ACCOUNT.sub(
        lambda match: "[ACCOUNT-" + "*" * max(4, len(match.group()) - 4) + "]", value
    )
