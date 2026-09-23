"""API tests: health, scheduling, infeasible status, locatable validation errors."""

from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def valid_payload() -> dict:
    return {
        "initial": {"time": 0, "azimuth": 0, "elevation": 0},
        "azimuth_speed": 1,
        "elevation_speed": 1,
        "targets": [
            {
                "id": "T1",
                "azimuth": 10,
                "elevation": 0,
                "duration": 100,
                "window_start": 0,
                "window_end": 1000,
                "priority": 1,
                "mandatory": False,
            },
            {
                "id": "T2",
                "azimuth": 20,
                "elevation": 0,
                "duration": 100,
                "window_start": 500,
                "window_end": 800,
                "priority": 2,
                "mandatory": True,
            },
            {
                "id": "T3",
                "azimuth": 30,
                "elevation": 0,
                "duration": 100,
                "window_start": 0,
                "window_end": 2000,
                "priority": 3,
                "mandatory": False,
            },
        ],
    }


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_schedule_ok_exact_optimum():
    resp = client.post("/api/schedule", json=valid_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["objective"] == {
        "total_priority": 6,
        "target_count": 3,
        "end_time": 600,
    }
    assert [s["target_id"] for s in body["steps"]] == ["T1", "T3", "T2"]
    assert body["unselected"] == []
    # phases are well-formed and waiting happens before T2's window
    t2 = body["steps"][2]
    assert t2["observe"] == {"start": 500, "end": 600}
    assert t2["wait"]["end"] == 500
    for step in body["steps"]:
        for phase in ("slew", "wait", "observe"):
            assert 0 <= step[phase]["start"] <= step[phase]["end"]


def test_schedule_infeasible_status():
    payload = valid_payload()
    payload["targets"][1]["window_end"] = 550  # mandatory T2 no longer fits
    resp = client.post("/api/schedule", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "infeasible"
    assert body["detail"]
    assert body["objective"] is None
    assert body["steps"] is None


def test_validation_error_is_locatable():
    payload = valid_payload()
    payload["targets"][2]["priority"] = 0
    resp = client.post("/api/schedule", json=payload)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert any(e["loc"][:2] == ["body", "targets"] and "priority" in e["loc"] for e in detail)


def test_duplicate_ids_rejected():
    payload = valid_payload()
    payload["targets"][1]["id"] = "T1"
    resp = client.post("/api/schedule", json=payload)
    assert resp.status_code == 422
    assert "T1" in resp.text


def test_window_order_rejected():
    payload = valid_payload()
    payload["targets"][0]["window_start"] = 900
    payload["targets"][0]["window_end"] = 100
    resp = client.post("/api/schedule", json=payload)
    assert resp.status_code == 422


def test_target_count_bounds():
    payload = valid_payload()
    payload["targets"] = payload["targets"][:1]
    assert client.post("/api/schedule", json=payload).status_code == 422

    payload = valid_payload()
    extra = copy.deepcopy(payload["targets"][0])
    payload["targets"] = payload["targets"] + [
        {**extra, "id": f"X{i}"} for i in range(14)
    ]
    assert len(payload["targets"]) == 17
    assert client.post("/api/schedule", json=payload).status_code == 422


def test_field_ranges_rejected():
    payload = valid_payload()
    payload["initial"]["time"] = 86400
    assert client.post("/api/schedule", json=payload).status_code == 422

    payload = valid_payload()
    payload["targets"][0]["azimuth"] = 360
    assert client.post("/api/schedule", json=payload).status_code == 422

    payload = valid_payload()
    payload["targets"][0]["elevation"] = 91
    assert client.post("/api/schedule", json=payload).status_code == 422

    payload = valid_payload()
    payload["azimuth_speed"] = 0
    assert client.post("/api/schedule", json=payload).status_code == 422

    payload = valid_payload()
    payload["targets"][0]["id"] = "   "
    assert client.post("/api/schedule", json=payload).status_code == 422


def test_missing_field_rejected():
    payload = valid_payload()
    del payload["initial"]
    resp = client.post("/api/schedule", json=payload)
    assert resp.status_code == 422
    assert any("initial" in e["loc"] for e in resp.json()["detail"])
