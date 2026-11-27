"""Deterministic registry-backed router used when no LLM key is configured."""

import re

from .entities import detect_language, resolve_bank, resolve_scheme

HINDI = {
    "widow": "\u0935\u093f\u0927\u0935\u093e", "pension": "\u092a\u0947\u0902\u0936\u0928",
    "ration": "\u0930\u093e\u0936\u0928", "udyam": "\u0909\u0926\u094d\u092f\u092e",
    "business": "\u0935\u094d\u092f\u0935\u0938\u093e\u092f", "loan": "\u0932\u094b\u0928",
    "kisan": "\u0915\u093f\u0938\u093e\u0928", "farmer": "\u0915\u093f\u0938\u093e\u0928",
    "deposit": "\u091c\u092e\u093e", "account": "\u0916\u093e\u0924\u093e",
}
BENGALI = {
    "widow": "\u09ac\u09bf\u09a7\u09ac\u09be", "pension": "\u09aa\u09c7\u09a8\u09b6\u09a8",
    "ration": "\u09b0\u09c7\u09b6\u09a8", "udyam": "\u0989\u09a6\u09cd\u09af\u09cb\u0997",
    "business": "\u09ac\u09cd\u09af\u09ac\u09b8\u09be", "loan": "\u098b\u09a3",
    "farmer": "\u0995\u09c3\u09b7\u0995", "deposit": "\u099c\u09ae\u09be",
}

RULES = [
    ("banking", "deposit", ("I want to add money", "taka save korte", "\u099c\u09ae\u09be\u09b0 \u09ab\u09b0\u09cd\u09ae", "\u09b8\u099e\09cd\09c7\u09af\u09bc"), 0.95),
    ("agriculture", "kcc_loan", ("chash er jonno", "\u09ab\u09b8\u09b2\u09c7\u09b0", "\u0995\u09c3\u09b7\u09bf \u098b\u09a3"), 0.94),
    ("msme", "msme_loan", ("loan for my company", "business ke liye loan", "company ke liye funding", "\u092a\u0942\u0902\u091c\u0940", "\u092b\u0902\u0921\u093f\u0902\u0917", "\u092e\u0942\u0932\u0927\u0928", "\u09ac\u09cd\u09af\09ac\09b8\u09be\09b0 \u099a\u09be\09b9\u09bf"), 0.93),
    ("social_welfare", "old_age_pension", ("apply for age pension", "old pension apply", "age benefit er", "\u09aa\u09cd\u09b0\u09ac\u09c0\09a3", "\u09ac\09af\09bc\09b8\09cd\0995"), 0.88),
    ("social_welfare", "widow_pension", ("widow", "vidhwa", "scheme batao", HINDI["widow"], BENGALI["widow"], "\u09ac\u09bf\u09a7\u09ac\u09be\u09b0"), 0.96),
    ("social_welfare", "old_age_pension", ("old age", "old pension", "age pension", "age benefit", "senior", "elder", "elderly", "retirement", "\u092c\u0941\u091c\u0941\u0930\u094d\u0917", "\u0935\u0943\u0926\u094d\u0927", "\u09aa\u09cd\u09b0\u09ac\u09c0\u09a3", "\u09ac\u09af\u09bc\u09b8\u09cd\u0995", HINDI["pension"], BENGALI["pension"]), 0.88),
    ("civil_services", "ration_card", ("ration", "food card", "food", "\u0916\u093e\u0926\u094d\u092f", "\u0996\u09be\u09a6\u09cd\u09af", HINDI["ration"], BENGALI["ration"]), 0.95),
    ("msme", "udyam", ("udyam", "msme registration", "business registration", "register my business", "register my company", "enterprise certificate", "registration", "register", "\u092a\u0902\u091c\u0940\u0915\u0930\u0923", "\u09a8\u09bf\u09ac\u09a8\u09cd\u09a7\u09a8", HINDI["udyam"], BENGALI["udyam"]), 0.95),
    ("msme", "msme_loan", ("business loan", "msme loan", "msme credit", "small business", "working capital", "business funding", "enterprise finance", "company loan", "shop expansion", "\u091b\u094b\u091f\u093e \u0915\u093e\u0930\u094b\u092c\u093e\u0930", "\u0926\u0941\u0915\u093e\u0928", HINDI["business"], BENGALI["business"]), 0.93),
    ("agriculture", "pm_kisan", ("pm kisan", "pm-kisan", "pm-kisan", "\u092a\u0940\u090f\u092e \u0915\u093f\u0938\u093e\u0928"), 0.96),
    ("agriculture", "kcc_loan", ("kisan credit", "kcc", "farmer loan", "farmer credit", "agri loan", "agriculture loan", "farming", "crop loan", "crops", "\u0916\u0947\u0924\u0940", "\u0915\u0943\u0937\u093f", "\u092b\u0938\u0932", "\u0995\u09c3\u09b7\u09bf \u098b\u09a3", "\u099a\u09be\u09b7\u09c7\u09b0", "chashi", HINDI["kisan"], BENGALI["farmer"]), 0.94),
    ("agriculture", "subsidy", ("subsidy", "\u0905\u0928\u0941\u0926\u093e\u0928", "\u09ad\u09b0\u09cd\u09a4\u09c1\u0995\u09bf"), 0.86),
    ("banking", "deposit", ("deposit", "jama", "save money", "savings", "save", "add money", "put money", "\u092c\u091a\u0924", "\u0938\u0902\u091a\u092f", "\u09b8\u099e\u09cd\u099a\u09af\u09bc", HINDI["deposit"], BENGALI["deposit"]), 0.95),
    ("banking", "loan", ("loan", "borrow", "udhaar", "udhar", "\u0909\u0927\u093e\u0930", "\u09a7\u09be\u09b0", HINDI["loan"], BENGALI["loan"]), 0.9),
    ("banking", "account", ("account", HINDI["account"], "\u0985\u09cd\u09af\u09be\u0995\u09be\u0989\u09a8\u09cd\u099f"), 0.82),
]


def route(text: str) -> dict:
    lowered = text.lower()
    selected = next(((d, s, c) for d, s, keys, c in RULES if any(_keyword_matches(lowered, k) for k in keys)), None)
    entities = {}
    if bank := resolve_bank(text):
        entities["bank"] = bank["id"]
    if scheme := resolve_scheme(text):
        entities["scheme"] = scheme["id"]
    if selected is None:
        return {"domain": None, "service": None, "action": "clarify", "entities": entities, "confidence": 0.0, "needs_clarification": True, "clarifying_question": _clarifying_question(detect_language(text))}
    domain, service, confidence = selected
    return {"domain": domain, "service": service, "action": "open_form", "entities": entities, "confidence": confidence, "needs_clarification": False, "clarifying_question": None}


def _keyword_matches(text: str, keyword: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(keyword.lower())}(?!\w)", text, flags=re.UNICODE) is not None


def _clarifying_question(language: str) -> str:
    return {"en": "Do you need a bank, scheme, pension, ration card, or business form?", "hi": "\u0906\u092a\u0915\u094b \u092c\u0948\u0902\u0915, \u092f\u094b\u091c\u0928\u093e, \u092a\u0947\u0902\u0936\u0928, \u0930\u093e\u0936\u0928 \u0915\u093e\u0930\u094d\u0921 \u092f\u093e \u0935\u094d\u092f\u093e\u092a\u093e\u0930 \u092b\u0949\u0930\u094d\u092e \u091a\u093e\u0939\u093f\u090f?", "bn": "\u0986\u09aa\u09a8\u09be\u09b0 \u09ac\u09cd\u09af\u09be\u0982\u0995, \u09aa\u09cd\u09b0\u0995\u09b2\u09cd\u09aa, \u09aa\u09c7\u09a8\u09b6\u09a8, \u09b0\u09c7\u09b6\u09a8 \u0995\u09be\u09b0\u09cd\u09a1 \u09a8\u09be \u09ac\u09cd\u09af\u09ac\u09b8\u09be\u09b0 \u09ab\u09b0\u09cd\u09ae \u09a6\u09b0\u0995\u09be\u09b0?"}.get(language, "What service do you need?")
