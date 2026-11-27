"""Token-based yes/no/correction classifier for confirmation questions.

Matches whole tokens after Unicode + punctuation normalisation, so STT casing,
trailing punctuation, fillers and extra words ("yes, it is correct") all work.
"""

from __future__ import annotations

import re
import unicodedata

AFFIRM = {
    "yes", "yeah", "yep", "yup", "ya", "correct", "right", "ok", "okay", "sure",
    "confirm", "confirmed", "absolutely", "definitely", "proceed", "continue",
    "haan", "han", "haa", "ha", "ji", "sahi", "sahih", "thik", "theek", "tik",
    "ache", "achhe", "achha", "accha", "bilkul", "ekdom", "hmm-ok",
    "हाँ", "हां", "हा", "जी", "सही", "ठीक", "बिल्कुल", "एकदम",
    "হ্যাঁ", "হ্যা", "জি", "ঠিক", "আছে", "একদম", "বেশ",
}
NEG = {
    "no", "nope", "nah", "nahi", "nahin", "nai", "na", "not", "never",
    "galat", "wrong", "incorrect", "bhul", "bhool", "vul", "cancel",
    "नहीं", "नही", "ना", "गलत", "না", "নাহি", "নেই", "ভুল",
}
PAD = {
    "it", "is", "that", "this", "was", "the", "answer", "you", "said", "i",
    "mean", "please", "go", "ahead", "do", "of", "course", "so", "very",
    "much", "kind", "for", "thats", "totally", "all", "good", "fine", "then",
    "hai", "hain", "he", "ho", "karo", "kar", "kijiye", "kijie", "dijiye",
    "कर", "करो", "दो", "दीजिए", "है", "हैं", "हो", "बोलिए", "बोलो",
    "বলুন", "করুন", "হবে", "করা", "এটা", "এটি",
}
CONTRAST = {
    "but", "however", "lekin", "magar", "par", "instead", "actually", "wait",
    "लेकिन", "मगर", "किंतु", "पर", "কিন্তু", "বরং",
}
FILLER = {"um", "umm", "uh", "uhh", "er", "erm", "hmm", "mm", "well", "like"}


def _tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    # Keep digits and letters, split everything else (commas inside numbers too).
    text = re.sub(r"[^\w\u0900-\u097f\u0980-\u09ff]+", " ", text)
    return [token for token in text.split() if token and token not in FILLER]


def classify_confirmation(text: str) -> str:
    """Return ``yes``, ``no``, ``correction`` or ``other``."""

    tokens = _tokens(text)
    if not tokens:
        return "other"
    negated_affirm = re.search(
        r"\b(not|isn'?t|no)\b\s+(correct|right|sahi|thik|theek|ok|okay)",
        " ".join(tokens),
    )
    if negated_affirm:
        return "no"
    has_yes = any(token in AFFIRM for token in tokens)
    has_no = any(token in NEG for token in tokens)
    has_contrast = any(token in CONTRAST for token in tokens)
    content = [
        token
        for token in tokens
        if token not in AFFIRM and token not in NEG and token not in PAD
        and token not in CONTRAST
    ]
    if has_yes and has_no:
        return "correction" if content or has_contrast else "other"
    if has_yes:
        return "correction" if content or has_contrast else "yes"
    if has_no:
        return "correction" if content else "no"
    return "correction" if has_contrast else "other"
