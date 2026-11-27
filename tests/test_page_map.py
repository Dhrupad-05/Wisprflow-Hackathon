"""Page field mapping: registry first, strict-JSON LLM only for ids, labels fallback."""

from fastapi.testclient import TestClient

from services.api.main import app
from services.api.page_map import map_page_fields

client = TestClient(app)


class Fake:
    def __init__(self, response):
        self.response = response

    def complete(self, _prompt):
        return self.response


FIELDS = [
    {"id": "account_no", "label": "Account number", "type": "text", "sensitive": False, "value": "SECRET"},
    {"id": "otp", "label": "One time code", "type": "text", "sensitive": False},
    {"id": "weird", "label": "Zorblax reference", "type": "text", "sensitive": False},
]


def test_registry_match_and_sensitive_flag_without_values():
    result = map_page_fields(FIELDS, "sbi_deposit_mock")
    mapping = {item["field"]: item for item in result["fields"]}
    assert mapping["account_no"]["registry_id"] == "account_no"
    assert mapping["account_no"]["source"] == "registry"
    assert mapping["otp"]["sensitive"] is True
    assert "SECRET" not in str(result)


def test_unmatched_field_falls_back_to_its_own_label():
    result = map_page_fields(FIELDS, "sbi_deposit_mock")
    mapping = {item["field"]: item for item in result["fields"]}
    assert mapping["weird"]["registry_id"] is None
    assert mapping["weird"]["label"] == "Zorblax reference"
    assert "weird" in result["unmatched"]


def test_llm_may_only_return_registry_field_ids():
    result = map_page_fields(
        FIELDS, "sbi_deposit_mock", client=Fake('{"mapping": [{"field": "weird", "registry_id": "amount"}]}')
    )
    mapping = {item["field"]: item for item in result["fields"]}
    assert mapping["weird"]["registry_id"] == "amount"
    assert mapping["weird"]["source"] == "llm"
    invented = map_page_fields(
        FIELDS, "sbi_deposit_mock", client=Fake('{"mapping": [{"field": "weird", "registry_id": "not_a_field"}]}')
    )
    weird = {item["field"]: item for item in invented["fields"]}["weird"]
    assert weird["registry_id"] is None
    assert weird["source"] == "label"


def test_invalid_llm_json_does_not_break_the_mapping():
    result = map_page_fields(FIELDS, "sbi_deposit_mock", client=Fake("not json"))
    weird = {item["field"]: item for item in result["fields"]}["weird"]
    assert weird["registry_id"] is None


def test_endpoint_accepts_schema_only():
    response = client.post(
        "/v1/page/fields",
        json={"portal_id": "kcc_loan_mock", "fields": FIELDS, "language": "hi"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["portal_id"] == "kcc_loan_mock"
    assert body["fields"]
    assert "SECRET" not in response.text
