from services.api.entities import parse_amount, parse_digits, resolve_bank, redact


def test_amount_cases():
    cases = {
        "paanch hazaar": 5000,
        "5 hajar": 5000,
        "five thousand": 5000,
        "5k": 5000,
        "₹5,000": 5000,
        "do sau pachas": 250,
        "panch sau": 500,
        "two thousand five hundred": 2500,
        "5000": 5000,
    }
    for text, want in cases.items():
        assert parse_amount(text) == want, (text, parse_amount(text))


def test_more_amounts():
    for text in [
        "one",
        "ten",
        "twenty",
        "fifty",
        "one hundred",
        "do hazaar",
        "teen hazaar",
        "चार हजार",
        "৫ হাজার",
        "2k",
        "10,000",
        "paanch sau pachaas",
    ]:
        assert parse_amount(text) is not None


def test_digits_and_bank_and_redaction():
    assert (
        parse_digits("double nine five one two three four five six seven eight")
        == "99512345678"
    )
    assert resolve_bank("esbiai")["id"] == "sbi"
    assert "123456" not in redact("otp 123456")
