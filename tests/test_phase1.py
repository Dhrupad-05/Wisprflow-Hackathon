"""Phase 1 gate coverage for the pure NLU layer."""

import pytest

from services.api.entities import (
    detect_language,
    match_command,
    parse_amount,
    parse_digits,
    redact,
    resolve_bank,
    resolve_scheme,
)
from services.api.router import route


AMOUNTS = [
    ("paanch hazaar", 5000),
    ("5 hajar", 5000),
    ("পাঁচ হাজার", 5000),
    ("पांच हजार", 5000),
    ("five thousand", 5000),
    ("5k", 5000),
    ("₹5,000", 5000),
    ("do sau pachas", 250),
    ("dhai hazaar", 2500),
    ("derh hazaar", 1500),
    ("sade teen hazaar", 3500),
    ("ek lakh", 100000),
    ("one lakh twenty thousand", 120000),
    ("paanch hazaar do sau", 5200),
    ("पांच हजार दो सौ", 5200),
    ("do hazaar paanch sau", 2500),
    ("one", 1),
    ("ten", 10),
    ("twenty", 20),
    ("fifty", 50),
    ("one hundred", 100),
    ("do hazaar", 2000),
    ("teen hazaar", 3000),
    ("चार हजार", 4000),
    ("৫ হাজার", 5000),
    ("2k", 2000),
    ("10,000", 10000),
    ("paanch sau pachaas", 550),
    ("two thousand five hundred", 2500),
    ("three hundred", 300),
    ("four hundred twenty", 420),
    ("six thousand", 6000),
    ("seven lakh", 700000),
    ("one crore", 10000000),
    ("nine hundred ninety", 990),
    ("do sau", 200),
    ("teen sau", 300),
    ("char sau", 400),
    ("paanch sau", 500),
    ("saat sau", 700),
    ("aath sau", 800),
    ("nau sau", 900),
    ("eleven", 11),
    ("twelve", 12),
    ("twenty five", 25),
    ("thirty two", 32),
    ("forty four", 44),
    ("sixty six", 66),
    ("ninety nine", 99),
    ("one lakh twenty", 100020),
    ("পাঁচশো", 500),
    ("দুই হাজার", 2000),
    ("তিনশো", 300),
    ("এক লাখ", 100000),
    ("दो हजार", 2000),
    ("तीन सौ", 300),
    ("एक लाख", 100000),
    ("₹ 12,500", 12500),
    ("75k", 75000),
    ("1.5k", 1500),
    ("2 lakh", 200000),
    ("ten thousand", 10000),
    ("one hundred twenty five", 125),
    ("do sau pachaas", 250),
]


@pytest.mark.parametrize("text, expected", AMOUNTS)
def test_amount_corpus(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("one two three four five six seven eight nine zero", "1234567890"),
        ("double nine five one two three four five six seven eight", "99512345678"),
        ("triple five", "555"),
        ("zero one two", "012"),
        ("ek do teen char", "1234"),
        ("paanch chhe saat aath nau", "56789"),
        ("এক দুই তিন চার পাঁচ", "12345"),
        ("एक दो तीन चार पाँच", "12345"),
        ("9876543210", "9876543210"),
        ("double 9 triple five", "99555"),
        ("oh one", "01"),
        ("nau zero", "90"),
        ("chaar teen", "43"),
        ("ছয় সাত আট", "678"),
        ("छह सात आठ", "678"),
        ("one nine", "19"),
        ("two eight", "28"),
        ("three seven", "37"),
        ("four six", "46"),
        ("five zero", "50"),
        ("six one", "61"),
        ("seven two", "72"),
        ("eight three", "83"),
        ("nine four", "94"),
    ],
)
def test_digit_corpus(text, expected):
    assert parse_digits(text) == expected


def test_digit_length_error():
    with pytest.raises(ValueError, match="expected 6 digits"):
        parse_digits("one two", expected_length=6)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("sbi", "sbi"),
        ("esbiai", "sbi"),
        ("state bank", "sbi"),
        ("pnb", "pnb"),
        ("punjab national", "pnb"),
        ("uco", "uco"),
        ("yuko", "uco"),
        ("bob", "bob"),
        ("baroda bank", "bob"),
        ("canara", "canara"),
        ("hdfc", "hdfc"),
        ("icici", "icici"),
        ("axis", "axis"),
        ("indian bank", "indian"),
        ("union bank", "union"),
        ("boi", "boi"),
        ("idbi", "idbi"),
        ("gramin bank", "grameen"),
        ("any bank", None),
        ("qwerty bank", None),
    ],
)
def test_bank_resolver(text, expected):
    result = resolve_bank(text)
    assert result is None if expected is None else result["id"] == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("yes", "yes"),
        ("haan", "yes"),
        ("হ্যাঁ", "yes"),
        ("हाँ", "yes"),
        ("no", "no"),
        ("nahi", "no"),
        ("না", "no"),
        ("नहीं", "no"),
        ("cancel", "cancel"),
        ("বাতিল", "cancel"),
        ("रद्द", "cancel"),
        ("back", "back"),
        ("repeat", "repeat"),
        ("pause", "pause"),
        ("help", "help"),
        ("forget everything", "forget"),
        ("সব ভুলে যাও", "forget"),
        ("I know it's fine", None),
        ("nobody says noone", None),
        ("yesterday", None),
    ],
)
def test_commands(text, expected):
    assert match_command(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Ami chashi, amar loan lagbe", "bn"),
        ("আমি কৃষক", "bn"),
        ("পাঁচ হাজার", "bn"),
        ("mujhe paanch hazaar chahiye", "hi"),
        ("मुझे मदद चाहिए", "hi"),
        ("पांच हजार", "hi"),
        ("I need help", "en"),
        ("please help me", "en"),
        ("bank account please", "en"),
        ("amar taka lagbe", "bn"),
        ("mujhe paisa chahiye", "hi"),
        ("chashi loan chai", "bn"),
        ("kisan loan chahiye", "hi"),
        ("what is this", "en"),
    ],
)
def test_language_detection(text, expected):
    assert detect_language(text) == expected


def test_scheme_redaction_and_routing():
    assert resolve_scheme("PM-KISAN status")["id"] == "pm_kisan"
    assert "123456" not in redact("otp 123456")
    assert "123456789012" not in redact("aadhaar 123456789012")
    assert "12345678901" not in redact("account 12345678901")
    assert route("asdf qwerty hmm")["service"] is None
    assert route("PM Kisan status dekhna hai")["service"] == "pm_kisan"
