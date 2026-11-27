"""Confirmation must advance, survive turns, and never repeat the same question."""

import pytest
from fastapi.testclient import TestClient

from services.api.main import app

client = TestClient(app)

OPENERS = {
    "en": "I need to borrow 50,000 from my SBI account",
    "hi": "मुझे SBI से 50,000 का लोन चाहिए",
    "bn": "আমার SBI থেকে 50,000 ঋণ লাগবে",
}
YES = {"en": "yes", "hi": "haan, sahi hai", "bn": "haan thik ache"}


def start(lang="en"):
    return client.post("/v1/session", json={"lang_hint": lang}).json()["session_id"]


def turn(session_id, text, trigger="typed"):
    response = client.post(
        "/v1/turn",
        json={"session_id": session_id, "transcript": text, "trigger": trigger},
    )
    assert response.status_code == 200, response.text
    return response.json()


def assert_advanced(response):
    assert response["state"] in {"PORTAL_OPEN", "NARROWING"}, response
    assert "is this correct" not in response["prompt_text"].lower(), response


@pytest.mark.parametrize("language", ["en", "hi", "bn"])
def test_confirmation_advances_in_all_languages(language):
    session_id = start(language)
    first = turn(session_id, OPENERS[language])
    assert first["state"] == "CONFIRMING_INTENT", first
    assert "50,000" in first["prompt_text"], first
    assert_advanced(turn(session_id, YES[language]))


def test_confirmation_survives_punctuation_case_and_filler():
    session_id = start("en")
    turn(session_id, OPENERS["en"])
    assert_advanced(turn(session_id, "Um, YES — it is correct."))


def test_correction_on_yes_but_changes_amount():
    session_id = start("en")
    turn(session_id, OPENERS["en"])
    corrected = turn(session_id, "yes but make it 40,000")
    assert corrected["state"] == "CONFIRMING_INTENT", corrected
    assert "40,000" in corrected["prompt_text"], corrected
    assert_advanced(turn(session_id, "yes, sahi hai"))


def test_negative_asks_what_to_change_once_then_requires_tap():
    session_id = start("en")
    turn(session_id, OPENERS["en"])
    rejected = turn(session_id, "no")
    assert rejected["state"] == "CONFIRMING_INTENT", rejected
    assert "change" in rejected["prompt_text"].lower(), rejected
    # A second rejection must never keep asking the same open question.
    stubborn = turn(session_id, "no")
    assert stubborn["state"] == "CONFIRMING_INTENT", stubborn
    assert stubborn["prompt_text"] != rejected["prompt_text"], stubborn
    assert stubborn["choices"], stubborn


def test_repeated_yes_after_advance_does_not_reask_or_reopen():
    session_id = start("en")
    turn(session_id, OPENERS["en"])
    advanced = turn(session_id, "yes")
    again = turn(session_id, "yes")
    assert advanced["state"] == again["state"] == "PORTAL_OPEN", again
    assert "is this correct" not in again["prompt_text"].lower(), again
    assert len([a for a in again["actions"] if a["type"] == "OPEN_PORTAL"]) <= 1


def test_three_confirmation_turns_never_repeat_the_same_prompt():
    session_id = start("en")
    prompts = [turn(session_id, OPENERS["en"])["prompt_text"]]
    prompts.append(turn(session_id, "hmm")["prompt_text"])
    prompts.append(turn(session_id, "what?")["prompt_text"])
    assert len(set(prompts)) == 3, prompts
    assert turn(session_id, "yes")["state"] in {"PORTAL_OPEN", "NARROWING"}
