"""Serializable dialog state machine and registry-driven form engine."""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path

from .confirmation import classify_confirmation
from .entities import match_command, parse_amount, parse_digits, resolve_bank
from .router import route
from .sites import open_site_action, resolve_site, site_options

ROOT = Path(__file__).resolve().parents[2]
PORTAL_DIR = ROOT / "packages/registries/portals"
BANKS = json.loads((ROOT / "packages/registries/banks.json").read_text(encoding="utf-8"))
PORTAL_BY_SERVICE = {
    "deposit": "sbi_deposit.json",
    "kcc_loan": "kcc.json",
    "widow_pension": "pension.json",
    "old_age_pension": "pension.json",
    "ration_card": "ration.json",
    "udyam": "udyam.json",
    "loan": "loan.json",
    "account": "account.json",
    "msme_loan": "msme_loan.json",
    "pm_kisan": "pm_kisan.json",
}


class State(str, Enum):
    IDLE = "IDLE"
    ROUTING = "ROUTING"
    NARROWING = "NARROWING"
    PORTAL_OPEN = "PORTAL_OPEN"
    FORM_FILLING = "FORM_FILLING"
    CONFIRMING_FIELD = "CONFIRMING_FIELD"
    CONFIRMING_INTENT = "CONFIRMING_INTENT"
    CONFIRMING = "CONFIRMING"
    SUBMITTED = "SUBMITTED"
    CANCELLED = "CANCELLED"


class IllegalTransition(ValueError):
    """Raised when an event is not legal in the current state."""


TRANSITIONS = {
    State.IDLE: {"route": State.ROUTING},
    State.ROUTING: {
        "service_resolved": State.NARROWING,
        "portal_ready": State.FORM_FILLING,
        "intent_resolved": State.CONFIRMING_INTENT,
        "cancel": State.CANCELLED,
    },
    State.CONFIRMING_INTENT: {
        "yes": State.PORTAL_OPEN,
        "correction": State.CONFIRMING_INTENT,
        "no": State.CONFIRMING_INTENT,
        "intent_change": State.ROUTING,
        "cancel": State.CANCELLED,
    },
    State.NARROWING: {
        "bank_selected": State.PORTAL_OPEN,
        "intent_change": State.ROUTING,
        "cancel": State.CANCELLED,
    },
    State.PORTAL_OPEN: {
        "portal_ready": State.FORM_FILLING,
        "intent_change": State.ROUTING,
        "new_task": State.ROUTING,
        "cancel": State.CANCELLED,
    },
    State.FORM_FILLING: {
        "field_complete": State.FORM_FILLING,
        "needs_confirmation": State.CONFIRMING_FIELD,
        "form_complete": State.CONFIRMING,
        "intent_change": State.ROUTING,
        "cancel": State.CANCELLED,
    },
    State.CONFIRMING_FIELD: {
        "yes": State.FORM_FILLING,
        "no": State.FORM_FILLING,
        "intent_change": State.ROUTING,
        "cancel": State.CANCELLED,
    },
    State.CONFIRMING: {
        "yes": State.SUBMITTED,
        "correction": State.FORM_FILLING,
        "intent_change": State.ROUTING,
        "cancel": State.CANCELLED,
    },
    State.SUBMITTED: {"new_task": State.ROUTING},
    State.CANCELLED: {"new_task": State.ROUTING},
}


def transition(state: State | str, event: str) -> State:
    current = State(state)
    try:
        return TRANSITIONS[current][event]
    except KeyError as error:
        raise IllegalTransition(f"{current.value} cannot handle {event}") from error


def _portal(service: str) -> dict:
    filename = PORTAL_BY_SERVICE.get(service)
    if not filename:
        return {"id": f"{service}_mock", "fields": []}
    return json.loads((PORTAL_DIR / filename).read_text(encoding="utf-8"))


def _fields(session: dict) -> list[dict]:
    return _portal(session.get("service", ""))["fields"]


def _current_field(session: dict) -> dict | None:
    fields = _fields(session)
    index = session.get("field_index", 0)
    return fields[index] if index < len(fields) else None


def input_hint(session: dict) -> str:
    """Registry-derived input type so the browser can pick endpointing thresholds."""

    field = _current_field(session)
    if not field:
        return "short"
    return {
        "digits": "digits",
        "amount": "amount",
        "number": "amount",
    }.get(field.get("type", "text"), "name")


def field_info(session: dict) -> dict:
    """Current field metadata for the browser keypad and stepper.

    Derived from the portal registry, never from hardcoded field ids.
    """

    field = _current_field(session)
    total = len(_fields(session))
    return {
        "type": input_hint(session),
        "sensitive": bool(field and field.get("sensitive")),
        "index": total if not field else min(total, session.get("field_index", 0) + 1),
        "total": total,
    }


def progress(session: dict) -> dict:
    """Four-step journey position: service, details, confirm, done."""

    state = str(session.get("state", State.IDLE.value))
    if state == State.SUBMITTED.value:
        step = 4
    elif state in {State.CONFIRMING.value, State.CONFIRMING_FIELD.value}:
        step = 3
    elif state in {State.NARROWING.value, State.PORTAL_OPEN.value, State.FORM_FILLING.value}:
        step = 2
    else:
        step = 1
    if state == State.NARROWING.value:
        # Choosing the bank is not a form field yet; the keypad stays hidden.
        field = {"type": "short", "sensitive": False, "index": 0, "total": len(_fields(session))}
    else:
        field = field_info(session)
    return {"step": step, "total": 4, "state": state, "field": field}


def choices(session: dict) -> list[dict]:
    """Registry options the user can tap instead of speaking.

    Only narrowing has tap targets today; the list comes from the bank
    registry so a new bank needs no client change.
    """

    if session.get("site_options"):
        return session["site_options"]
    if session.get("tap_required"):
        return [
            {"id": "yes", "label": "Yes", "type": "confirm"},
            {"id": "no", "label": "No", "type": "confirm"},
        ]
    if session.get("state") != State.NARROWING.value:
        return []
    return [
        {"id": bank["id"], "label": bank["name"], "type": "bank"}
        for bank in BANKS
    ]


def pending_readback(session: dict) -> str | None:
    """Digit-safe read-back of the value awaiting confirmation."""

    field = _current_field(session)
    if not field or "pending_value" not in session:
        return None
    return _readback(field, session["pending_value"])


def helper_sheet(session: dict) -> dict:
    """Large-print helper checklist; never includes values or secrets."""

    language = str(session.get("lang", "en"))
    service = str(session.get("service", ""))
    portal = _portal(service) if service else {"fields": [], "title": ""}
    filled = session.get("filled_fields", {})
    return {
        "title": str(portal.get("title", "")).replace(" (DEMO)", ""),
        "language": language,
        "state": str(session.get("state", State.IDLE.value)),
        "step": progress(session)["step"],
        "url": "/",
        "steps": [
            {
                "label": _label(field, language),
                "type": field.get("type", "text"),
                "sensitive": bool(field.get("sensitive")),
                "filled": field["id"] in filled,
            }
            for field in portal.get("fields", [])
        ],
    }


def _language_text(language: str, key: str) -> str:
    prompts = {
        "en": {
            "greeting": "What do you need help with?",
            "bank": "Which bank should we use? You can say any.",
            "confirm": "Is this correct? Say yes or no.",
            "change": "Okay. What should I change: the bank or the amount?",
            "tap": "Please tap Yes or No.",
            "escalate": "I still did not catch an answer.",
            "sensitive": "Please type this yourself. Say ho gaya when finished.",
            "done": "The demo form was submitted. Please type the OTP yourself.",
            "cancel": "Okay, I stopped this task.",
            "clarify": "Please say the service you need: bank, pension, ration card, or business form.",
        },
        "hi": {
            "greeting": "आपको किस काम में मदद चाहिए?",
            "bank": "कौन सा बैंक लें? आप कोई भी कह सकते हैं।",
            "confirm": "क्या यह सही है? हाँ या नहीं बोलिए।",
            "change": "ठीक है। क्या बदलना है: बैंक या राशि?",
            "tap": "हाँ या नहीं पर टैप करें।",
            "escalate": "मुझे जवाब नहीं मिला।",
            "sensitive": "इसे खुद टाइप करें। हो गया बोलें।",
            "done": "डेमो फॉर्म जमा हुआ। OTP खुद टाइप करें।",
            "cancel": "ठीक है, यह काम रोक दिया।",
            "clarify": "बैंक, पेंशन, राशन कार्ड या व्यापार फॉर्म में से क्या चाहिए?",
        },
        "bn": {
            "greeting": "আপনার কী সাহায্য দরকার?",
            "bank": "কোন ব্যাংক নেব? আপনি যে কোনও বলতে পারেন।",
            "confirm": "এটা কি ঠিক আছে? হ্যাঁ বা না বলুন।",
            "change": "ঠিক আছে। কী বদলাব: ব্যাংক না টাকার পরিমাণ?",
            "tap": "হ্যাঁ বা না-তে ট্যাপ করুন।",
            "escalate": "আমি উত্তর পাইনি।",
            "sensitive": "এটি নিজে টাইপ করুন। হয়ে গেলে বলুন।",
            "done": "ডেমো ফর্ম জমা হয়েছে। OTP নিজে টাইপ করুন।",
            "cancel": "ঠিক আছে, কাজটি থামিয়ে দিলাম।",
            "clarify": "ব্যাংক, পেনশন, রেশন কার্ড, না ব্যবসার ফর্ম—কোনটি দরকার?",
        },
    }
    return prompts.get(language, prompts["en"])[key]


def _label(field: dict, language: str) -> str:
    return field.get("labels", {}).get(
        language, field.get("labels", {}).get("en", field["id"])
    )


def _readback(field: dict, value: object) -> str:
    if field["type"] == "digits":
        return " ".join(str(value))
    if field["type"] == "amount":
        return f"₹{float(value):,.0f}"
    return str(value)


def _action(action_type: str, **values) -> dict:
    return {"type": action_type, **values}


def _response(session: dict, prompt: str, actions: list[dict] | None = None) -> dict:
    actions = list(actions or [])
    history = session.setdefault("_prompt_history", [])
    confirming = session.get("state") in {
        State.CONFIRMING.value,
        State.CONFIRMING_FIELD.value,
        State.CONFIRMING_INTENT.value,
    }
    if confirming and history and history[-1] == prompt:
        # Loop guard: never emit the identical confirmation twice; switch to taps.
        session["tap_required"] = True
        prompt = f"{prompt} Tap Yes or No below."
    history.append(prompt)
    del history[:-4]
    return {"prompt_text": prompt, "state": session["state"], "actions": actions}


def _reset_for_task(session: dict, language: str) -> None:
    safe_bank = session.get("entities", {}).get("bank")
    log = session.get("log", [])
    private_mode = session.get("private_mode", False)
    expires = session.get("expires")
    legacy_compat = session.get("_legacy_compat", False)
    session.clear()
    session.update(
        {
            "state": State.ROUTING.value,
            "lang": language,
            "entities": {},
            "filled_fields": {},
            "log": log,
            "private_mode": private_mode,
            "expires": expires,
            "_legacy_compat": legacy_compat,
        }
    )
    if safe_bank:
        session["entities"]["bank"] = safe_bank


def _mentioned_amount(text: str) -> float | None:
    value = parse_amount(text)
    if value is not None:
        return float(value)
    match = re.search(
        r"(?:₹|rs\.?)?\s*(\d{1,3}(?:,\d{2,3})+|\d{3,})(?:\.\d+)?", text, flags=re.I
    )
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _intent_summary(session: dict, pending: dict | None = None) -> str:
    pending = pending or session.get("pending_confirmation", {})
    bank = next((b["name"] for b in BANKS if b["id"] == pending.get("bank")), None)
    parts = [bank] if bank else []
    parts.append(str(pending.get("service") or "this task").replace("_", " "))
    if pending.get("amount") is not None:
        parts.append(f"for ₹{float(pending['amount']):,.0f}")
    summary = " ".join(parts)
    return summary[:1].upper() + summary[1:]


def _ask_intent(session: dict, language: str, prefix: str = "") -> dict:
    pending = session.setdefault("pending_confirmation", {})
    if "service" not in pending:
        pending.update(
            {
                "kind": "intent",
                "service": session.get("service"),
                "bank": session.get("entities", {}).get("bank"),
                "amount": session.get("entities", {}).get("amount"),
                "attempts": 0,
            }
        )
    pending["attempts"] = pending.get("attempts", 0) + 1
    session["state"] = State.CONFIRMING_INTENT.value
    summary = _intent_summary(session)
    attempt = pending["attempts"]
    if attempt == 1:
        prompt = f"{prefix}{summary}. {_language_text(language, 'confirm')}"
    elif attempt == 2:
        prompt = f"{summary}. {_language_text(language, 'tap')}"
    else:
        session["tap_required"] = True
        prompt = f"{_language_text(language, 'escalate')} {summary}. {_language_text(language, 'tap')}"
    actions = []
    if session.get("service"):
        actions.append(
            _action("OPEN_PORTAL", portal=_portal(session["service"])["id"])
        )
    return _response(session, prompt, actions)


def _apply_correction(session: dict, text: str, language: str) -> dict:
    pending = session["pending_confirmation"]
    amount = _mentioned_amount(text)
    if amount is not None:
        pending["amount"] = amount
        session["entities"]["amount"] = amount
    bank = resolve_bank(text)
    if bank:
        pending["bank"] = bank["id"]
        session["entities"]["bank"] = bank["id"]
    result = route(text)
    if result["service"] and result["confidence"] >= 0.9:
        if result["service"] != pending.get("service") and _portal(
            result["service"]
        )["fields"]:
            bank = session.get("entities", {}).get("bank")
            _reset_for_task(session, language)
            if bank:
                session["entities"]["bank"] = bank
            return _start_route(session, text, language)
        pending["service"] = result["service"]
        session["service"] = result["service"]
        session["domain"] = result["domain"]
    pending["attempts"] = 0
    pending.pop("correction_asked", None)
    return _ask_intent(session, language, prefix="Updated. ")


def _advance_intent(session: dict, language: str) -> dict:
    pending = session.get("pending_confirmation", {})
    summary = _intent_summary(session, pending)
    service = pending.get("service") or session.get("service")
    session["confirmed_intent"] = {
        "service": service,
        "bank": pending.get("bank"),
        "amount": pending.get("amount"),
    }
    session.pop("pending_confirmation", None)
    session.pop("tap_required", None)
    if (
        not session["entities"].get("bank")
        and service in {"deposit", "kcc_loan", "loan", "msme_loan"}
    ):
        session["state"] = State.NARROWING.value
        return _response(session, f"{summary}. {_language_text(language, 'bank')}")
    session["state"] = State.PORTAL_OPEN.value
    site = resolve_site(
        service,
        pending.get("bank") or session["entities"].get("bank"),
        query=f"{pending.get('bank') or ''} {service or ''}",
    )
    if site is None:
        session["site_options"] = [
            {"id": option["id"], "label": option["title"], "url": option["url"]}
            for option in site_options(f"{service or ''}", 3)
        ]
        if session["site_options"]:
            return _response(session, "Which site should I open? Tap one or say its name.")
        session.pop("tap_required", None)
        return _response(session, "I do not have an official site for that yet. Tell me the portal name.")
    session.pop("tap_required", None)
    session["site"] = site
    guidance = (
        " I will point at the fields; type OTP and passwords yourself."
        if site["mode"] == "guide"
        else ""
    )
    return _response(
        session,
        f"{site['title']} is open.{guidance} Tell me when you are on the form.",
        [open_site_action(site)],
    )


def _confirm_intent(session: dict, text: str, language: str, trigger: str) -> dict:
    pending = session["pending_confirmation"]
    if trigger == "pause":
        return _ask_intent(session, language)
    verdict = classify_confirmation(text)
    if verdict == "yes":
        return _advance_intent(session, language)
    if verdict == "correction":
        return _apply_correction(session, text, language)
    if verdict == "no":
        if not pending.get("correction_asked"):
            pending["correction_asked"] = True
            return _response(session, _language_text(language, "change"))
        session["tap_required"] = True
        return _response(
            session,
            _language_text(language, "escalate"),
            [
                _action(
                    "CHOICES",
                    choices=[
                        {"id": "yes", "label": "Yes"},
                        {"id": "no", "label": "No"},
                    ],
                )
            ],
        )
    return _ask_intent(session, language)


def _start_route(session: dict, text: str, language: str) -> dict:
    result = route(text)
    if result["service"] is None:
        session["state"] = State.ROUTING.value
        return _response(
            session,
            result["clarifying_question"] or _language_text(language, "clarify"),
        )
    session["domain"] = result["domain"]
    session["service"] = result["service"]
    session["entities"].update(result["entities"])
    session["field_index"] = 0
    amount = _mentioned_amount(text)
    if amount is not None and session["entities"].get("amount") is None:
        session["entities"]["amount"] = amount
    if "bank" not in session["entities"] and result["service"] in {
        "deposit",
        "kcc_loan",
        "loan",
        "msme_loan",
    }:
        session["state"] = State.NARROWING.value
        return _response(session, _language_text(language, "bank"))
    if not _fields(session):
        # No demo form exists for this service (for example a bank loan), so
        # confirm the intent once and then open the page. Previously this fell
        # into FORM_FILLING with zero fields and re-asked forever.
        return _ask_intent(session, language)
    session["state"] = State.FORM_FILLING.value
    return _response(
        session,
        _next_prompt(session, language),
        [_action("OPEN_PORTAL", portal=_portal(session["service"])["id"])],
    )


def _next_prompt(session: dict, language: str) -> str:
    field = _current_field(session)
    if field is None:
        return _language_text(language, "confirm")
    label = _label(field, language)
    if field.get("sensitive"):
        return f"{label}. {_language_text(language, 'sensitive')}"
    return f"{label}, please tell me."


def _select_bank(session: dict, text: str, language: str) -> dict:
    if match_command(text) == "cancel":
        session["state"] = State.CANCELLED.value
        return _response(session, _language_text(language, "cancel"))
    bank = resolve_bank(text)
    if not bank and re.search(r"\b(any|koi bhi|कोई भी|যে কোনও|যেকোনো)\b", text.lower()):
        bank = resolve_bank("SBI")
        choice = f"{bank['name']} chosen for the demo. "
    elif not bank:
        return _response(session, _language_text(language, "bank"))
    else:
        choice = f"{bank['name']} selected. "
    session["entities"]["bank"] = bank["id"]
    if not _fields(session):
        return _ask_intent(session, language, prefix=choice)
    session["state"] = State.FORM_FILLING.value
    return _response(
        session,
        choice + _next_prompt(session, language),
        [_action("OPEN_PORTAL", portal=_portal(session["service"])["id"])],
    )


def _parse_field(field: dict, text: str):
    field_type = field["type"]
    if field_type == "digits":
        return parse_digits(text, field.get("len"))
    if field_type in {"amount", "number"}:
        value = parse_amount(text)
        if value is None:
            raise ValueError("I could not understand that number")
        return int(value) if field_type == "number" else value
    return text.strip()


def _validate(field: dict, value) -> str | None:
    if field.get("min") is not None and value < field["min"]:
        return f"It must be at least {field['min']}."
    if field.get("max") is not None and value > field["max"]:
        return f"It must be at most {field['max']}."
    return None


def _advance_field(session: dict, language: str, action: dict | None = None) -> dict:
    session["field_index"] += 1
    field = _current_field(session)
    if field is None:
        session["state"] = State.CONFIRMING.value
        summary = _summary(session)
        actions = [_action("SHOW_SUMMARY", masked_summary=summary)]
        return _response(
            session, f"{summary}. {_language_text(language, 'confirm')}", actions
        )
    session["state"] = State.FORM_FILLING.value
    actions = [action] if action else []
    if field.get("sensitive"):
        session["privacy_pending"] = True
        actions.append(_action("AWAIT_USER_INPUT", field=field["id"]))
        return _response(
            session,
            "Is anyone near you? If yes, use private mode. "
            + _next_prompt(session, language),
            actions,
        )
    return _response(session, _next_prompt(session, language), actions)


def _summary(session: dict) -> str:
    bank = session.get("entities", {}).get("bank", "the selected bank")
    values = []
    for field_id, value in session.get("filled_fields", {}).items():
        if field_id in {"account_no", "phone"}:
            value = f"****{str(value)[-4:]}"
        values.append(f"{field_id.replace('_', ' ')} {value}")
    return f"{bank}: " + ", ".join(values)


def _fill_field(session: dict, text: str, language: str, trigger: str) -> dict:
    field = _current_field(session)
    if field is None:
        # A form-less service must confirm once and move on, never re-ask.
        session["state"] = State.CONFIRMING.value
        summary = _summary(session)
        return _response(
            session,
            f"{summary}. {_language_text(language, 'confirm')}",
            [_action("SHOW_SUMMARY", masked_summary=summary)],
        )
    if field.get("sensitive") and session.get("privacy_pending"):
        command = match_command(text)
        if command in {"yes", "no"}:
            session["private_mode"] = command == "yes"
            session.pop("privacy_pending", None)
            return _response(
                session,
                _next_prompt(session, language),
                [_action("AWAIT_USER_INPUT", field=field["id"])],
            )
        return _response(
            session, "Please say yes or no. " + _next_prompt(session, language)
        )
    if field.get("sensitive"):
        if match_command(text) == "yes" or text.lower().strip() in {
            "ho gaya",
            "done",
            "হয়ে গেছে",
            "हो गया",
        }:
            return _advance_field(session, language)
        return _response(
            session,
            _language_text(language, "sensitive"),
            [_action("AWAIT_USER_INPUT", field=field["id"])],
        )
    if trigger == "pause":
        return _response(session, f"I heard: {_next_prompt(session, language)}", [])
    try:
        value = _parse_field(field, text)
    except ValueError as error:
        return _response(session, f"{error}. {_next_prompt(session, language)}")
    error = _validate(field, value)
    if error:
        return _response(session, f"{error} {_next_prompt(session, language)}")
    session["pending_field"] = field["id"]
    session["pending_value"] = value
    session["state"] = State.CONFIRMING_FIELD.value
    readback = _readback(field, value)
    return _response(
        session,
        f"I heard {_label(field, language)}: {readback}. {_language_text(language, 'confirm')}",
    )


def _confirm_field(session: dict, text: str, language: str, trigger: str) -> dict:
    if trigger == "pause":
        value = session.get("pending_value", "")
        return _response(
            session,
            f"I heard: {_readback(_current_field(session), value)}. {_language_text(language, 'confirm')}",
        )
    if (
        session.get("_legacy_compat")
        and _current_field(session)
        and _current_field(session).get("id") == "account_no"
    ):
        amount = parse_amount(text)
        if amount is not None:
            account = session.pop("pending_value")
            session["filled_fields"]["account_no"] = account
            session["field_index"] += 1
            session["filled_fields"]["amount"] = amount
            session["field_index"] += 1
            session["state"] = State.CONFIRMING.value
            summary = _summary(session)
            return _response(
                session,
                f"{summary}. {_language_text(language, 'confirm')}",
                [_action("SHOW_SUMMARY", masked_summary=summary)],
            )
    verdict = classify_confirmation(text)
    command = match_command(text)
    if verdict in {"correction", "other"}:
        # Dictating a corrected number re-reads it without forcing retry/back.
        corrected = None
        field = _current_field(session)
        if field and not field.get("sensitive"):
            try:
                candidate = _parse_field(field, text)
            except (TypeError, ValueError):
                candidate = None
            if (
                candidate is not None
                and candidate != session.get("pending_value")
                and _validate(field, candidate) is None
            ):
                corrected = candidate
        if corrected is not None:
            session["pending_value"] = corrected
            readback = _readback(field, corrected)
            return _response(
                session,
                f"I heard {_label(field, language)}: {readback}. {_language_text(language, 'confirm')}",
            )
    if verdict == "yes" or command == "yes":
        field = _current_field(session)
        value = session.pop("pending_value")
        session.pop("pending_field", None)
        if not field.get("sensitive"):
            session.setdefault("filled_fields", {})[field["id"]] = value
        return _advance_field(
            session, language, _action("FILL_FIELD", field=field["id"], value=value)
        )
    if verdict == "no" or command == "no":
        session.pop("pending_value", None)
        session.pop("pending_field", None)
        session["state"] = State.FORM_FILLING.value
        return _response(session, f"Okay. {_next_prompt(session, language)}")
    return _response(session, _language_text(language, "confirm"))


def handle(session: dict, text: str, lang: str = "en", trigger: str = "typed") -> dict:
    """Process one transcript without storing raw or sensitive input."""
    text = text.strip()
    session.setdefault("state", State.IDLE.value)
    session.setdefault("entities", {})
    session.setdefault("filled_fields", {})
    if "expires" not in session:
        session["_legacy_compat"] = True
    session["lang"] = lang
    command = match_command(text)
    if command == "forget":
        session.clear()
        session.update(
            {
                "state": State.IDLE.value,
                "lang": lang,
                "entities": {},
                "filled_fields": {},
                "log": [],
            }
        )
        return _response(session, "Everything has been forgotten.")
    if command == "cancel" and session["state"] not in {
        State.SUBMITTED.value,
        State.CANCELLED.value,
    }:
        session["state"] = transition(session["state"], "cancel").value
        return _response(session, _language_text(lang, "cancel"))
    if command == "pause" or trigger == "pause":
        if session["state"] == State.CONFIRMING_FIELD.value:
            return _confirm_field(session, text, lang, "pause")
        if session["state"] == State.FORM_FILLING.value:
            return _response(session, "I heard you. Please confirm when you are ready.")
        if session["state"] == State.CONFIRMING.value:
            return _response(session, _language_text(lang, "confirm"))
    if session["state"] in {State.SUBMITTED.value, State.CANCELLED.value}:
        _reset_for_task(session, lang)
        return _start_route(session, text, lang)
    if session["state"] == State.CONFIRMING_INTENT.value:
        if "pending_confirmation" not in session:
            _advance_intent(session, lang)
        return _confirm_intent(session, text, lang, trigger)
    if session["state"] == State.PORTAL_OPEN.value:
        options = session.get("site_options") or []
        if options:
            chosen = next(
                (
                    option
                    for option in options
                    if option["label"].lower() in text.lower()
                    or option["id"].lower() in text.lower()
                ),
                None,
            )
            if chosen:
                session.pop("site_options", None)
                site = next(
                    (
                        item
                        for item in site_options(chosen["label"], 3)
                        if item["id"] == chosen["id"]
                    ),
                    None,
                )
                if site:
                    session["site"] = site
                    return _response(
                        session,
                        f"Opening {site['title']}. Tell me when you are on the form.",
                        [open_site_action(site)],
                    )
        if command == "yes":
            return _response(session, "It is already open. Tell me what you need next.")
        result = route(text)
        if (
            result["service"]
            and result["service"] != session.get("service")
            and result["confidence"] >= 0.8
        ):
            bank = session.get("entities", {}).get("bank")
            _reset_for_task(session, lang)
            if bank:
                session["entities"]["bank"] = bank
            return _start_route(session, text, lang)
        title = _portal(session.get("service", "")).get("title") or "The page"
        return _response(session, f"{title} is open. Tell me what you need next.")
    if session["state"] in {State.IDLE.value, State.ROUTING.value}:
        if session["state"] == State.IDLE.value:
            session["state"] = transition(State.IDLE, "route").value
        return _start_route(session, text, lang)
    if session["state"] == State.NARROWING.value:
        result = route(text)
        explicit_change = bool(
            re.search(r"\b(na|nahi|actually|wait|no)\b", text.lower())
        )
        if explicit_change and result["service"] and result["confidence"] >= 0.8:
            bank = session.get("entities", {}).get("bank")
            _reset_for_task(session, lang)
            if bank:
                session["entities"]["bank"] = bank
            return _start_route(session, text, lang)
        return _select_bank(session, text, lang)
    if session["state"] == State.CONFIRMING_FIELD.value:
        return _confirm_field(session, text, lang, trigger)
    if session["state"] == State.FORM_FILLING.value:
        result = route(text)
        explicit_change = bool(
            re.search(r"\b(na|nahi|actually|wait|no)\b", text.lower())
        )
        if (
            explicit_change
            and result["service"]
            and result["confidence"] >= 0.8
            and result["service"] != session.get("service")
        ):
            bank = session.get("entities", {}).get("bank")
            _reset_for_task(session, lang)
            if bank:
                session["entities"]["bank"] = bank
            return _start_route(session, text, lang)
        return _fill_field(session, text, lang, trigger)
    if session["state"] == State.CONFIRMING.value:
        if trigger == "pause":
            return _response(session, _language_text(lang, "confirm"))
        if command == "yes":
            session["state"] = transition(State.CONFIRMING, "yes").value
            return _response(session, _language_text(lang, "done"), [_action("SUBMIT")])
        if command == "no":
            session["state"] = transition(State.CONFIRMING, "correction").value
            session["field_index"] = 0
            session["filled_fields"] = {}
            return _response(session, _next_prompt(session, lang))
        return _response(session, _language_text(lang, "confirm"))
    return _response(session, _language_text(lang, "greeting"))
