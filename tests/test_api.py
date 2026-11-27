from fastapi.testclient import TestClient
from services.api.main import app

client = TestClient(app)


def test_api_flow_and_wipe():
    sid = client.post("/v1/session", json={"lang_hint": "bn"}).json()["session_id"]
    r = client.post(
        "/v1/turn", json={"session_id": sid, "transcript": "taka jama dite chai"}
    )
    assert r.status_code == 200
    assert client.get("/v1/session/" + sid + "/log").status_code == 200
    assert client.post("/v1/session/" + sid + "/wipe").json()["wiped"] is True
    assert client.get("/v1/session/" + sid + "/log").status_code == 404
