from services.api.dialog import handle


def test_deposit_confirmation_gate_and_reroute():
    s = {"state": "IDLE", "entities": {}, "log": []}
    handle(s, "Ami chashi amar loan lagbe")
    assert s["service"] == "kcc_loan"
    handle(s, "Na, taka jama dite chai")
    assert s["service"] == "deposit"
    handle(s, "SBI")
    handle(s, "one two three four five six seven eight nine zero one")
    handle(s, "paanch hazaar")
    assert s["state"] == "CONFIRMING"
    assert handle(s, "pause")["state"] == "CONFIRMING"
    assert handle(s, "haan")["state"] == "SUBMITTED"


def test_wipe():
    s = {"state": "FORM_FILLING", "log": [{"heard": "x"}]}
    out = handle(s, "forget everything")
    assert out["state"] == "IDLE" and s["log"] == []
