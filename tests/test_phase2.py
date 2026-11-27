"""Phase 2 integration, state-machine, and safety gates."""

from fastapi.testclient import TestClient
import pytest

from services.api.dialog import IllegalTransition, State, transition
from services.api.main import app, sessions


client = TestClient(app)


def start(lang="en"):
    return client.post("/v1/session", json={"lang_hint": lang}).json()["session_id"]


def turn(session_id, text, trigger="typed"):
    response = client.post(
        "/v1/turn",
        json={"session_id": session_id, "transcript": text, "trigger": trigger},
    )
    assert response.status_code == 200, response.text
    return response.json()


def confirm_deposit(session_id):
    turn(session_id, "Ami chashi amar loan lagbe")
    turn(session_id, "SBI")
    turn(session_id, "Na, taka jama dite chai")
    account = turn(session_id, "one two three four five six seven eight nine zero one")
    assert account["state"] == "CONFIRMING_FIELD"
    assert turn(session_id, "pause", "pause")["state"] == "CONFIRMING_FIELD"
    turn(session_id, "haan")
    turn(session_id, "paanch hazaar")
    turn(session_id, "haan")


def finish_sensitive(session_id, private_answer="no"):
    assert turn(session_id, private_answer)["state"] == "FORM_FILLING"
    assert "123456" not in str(turn(session_id, "123456"))
    return turn(session_id, "ho gaya")


def test_e1_farmer_changes_mind_and_submits_only_after_yes():
    session_id = start("bn")
    confirm_deposit(session_id)
    summary = finish_sensitive(session_id)
    assert summary["state"] == "CONFIRMING"
    assert "account no ****8901" in summary["prompt_text"]
    assert turn(session_id, "pause", "pause")["state"] == "CONFIRMING"
    assert turn(session_id, "haan")["state"] == "SUBMITTED"


@pytest.mark.parametrize(
    "language, opening",
    [
        ("en", "I am a farmer, I need a loan"),
        ("hi", "मैं किसान हूँ, मुझे लोन चाहिए"),
        ("bn", "আমি কৃষক, আমার ঋণ লাগবে"),
        ("bn", "Ami chashi, amar loan lagbe"),
    ],
)
def test_e1_language_variants_print_transcript(language, opening, capsys):
    session_id = start(language)
    first = turn(session_id, opening)
    second = turn(session_id, "SBI")
    third = turn(session_id, "Na, taka jama dite chai")
    safe_opening = opening.encode("unicode_escape").decode("ascii")
    print(
        f"{language}: {safe_opening} -> {first['state']} -> "
        f"{second['state']} -> {third['state']}"
    )
    assert first["state"] == "NARROWING"
    assert second["actions"][0]["type"] == "OPEN_PORTAL"
    assert third["actions"][0]["portal"] == "sbi_deposit_mock"


def test_e2_widow_pension():
    session_id = start("hi")
    assert turn(session_id, "विधवा पेंशन")["state"] == "FORM_FILLING"
    turn(session_id, "Savitri Devi")
    turn(session_id, "हाँ")
    turn(session_id, "65")
    turn(session_id, "हाँ")
    finish_sensitive(session_id, "नहीं")
    assert turn(session_id, "हाँ")["state"] == "SUBMITTED"


def test_e3_ration_and_e4_udyam_route_to_distinct_forms():
    ration = start()
    assert turn(ration, "ration card")["actions"][0]["portal"] == "ration_mock"
    udyam = start()
    assert turn(udyam, "Udyam registration")["actions"][0]["portal"] == "udyam_mock"


def test_e5_any_bank_selects_a_demo_bank():
    session_id = start()
    response = turn(session_id, "farmer loan")
    assert response["state"] == "NARROWING"
    response = turn(session_id, "any")
    assert "State Bank" in response["prompt_text"]
    assert response["actions"][0]["type"] == "OPEN_PORTAL"


def test_e6_cancel_and_forget_everything():
    session_id = start()
    assert turn(session_id, "deposit")["state"] == "NARROWING"
    assert turn(session_id, "cancel")["state"] == "CANCELLED"
    assert turn(session_id, "forget everything")["state"] == "IDLE"
    assert sessions[session_id]["filled_fields"] == {}


def test_e7_digit_correction_does_not_advance():
    session_id = start()
    turn(session_id, "deposit")
    turn(session_id, "SBI")
    turn(session_id, "one two three four five six seven eight nine zero one")
    correction = turn(session_id, "nahi")
    assert correction["state"] == "FORM_FILLING"
    assert "account" in correction["prompt_text"].lower()
    assert sessions[session_id]["filled_fields"] == {}


def test_illegal_transitions_are_rejected():
    with pytest.raises(IllegalTransition):
        transition(State.IDLE, "yes")
    with pytest.raises(IllegalTransition):
        transition(State.SUBMITTED, "yes")
    assert transition(State.CONFIRMING, "yes") == State.SUBMITTED


def test_pause_cannot_submit_or_advance_sensitive_field():
    session_id = start()
    turn(session_id, "deposit")
    turn(session_id, "SBI")
    turn(session_id, "one two three four five six seven eight nine zero one")
    turn(session_id, "haan")
    turn(session_id, "paanch hazaar")
    response = turn(session_id, "haan")
    assert response["state"] == "FORM_FILLING"
    paused = turn(session_id, "", "pause")
    assert paused["state"] == "FORM_FILLING"
    assert not any(action["type"] == "SUBMIT" for action in paused["actions"])


def test_sensitive_value_is_not_in_session_or_log():
    session_id = start()
    turn(session_id, "deposit")
    turn(session_id, "SBI")
    turn(session_id, "one two three four five six seven eight nine zero one")
    turn(session_id, "haan")
    turn(session_id, "paanch hazaar")
    turn(session_id, "haan")
    turn(session_id, "no")
    turn(session_id, "123456")
    assert "otp" not in sessions[session_id]
    assert "123456" not in str(client.get(f"/v1/session/{session_id}/log").json())
