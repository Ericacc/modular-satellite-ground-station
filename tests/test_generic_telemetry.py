import json

from fastapi.testclient import TestClient

from aegissat.api import app
from aegissat.generic_telemetry import (
    archive_generic_telemetry,
    build_generic_telemetry,
    flatten_parameters,
)
from aegissat.services.telemetry import TelemetryService
from aegissat.storage.repository import MemoryRepository


def test_unknown_and_nested_fields_are_kept_without_configuration():
    decoded = {
        "EPS": {"battery_voltage": 4.12},
        "new_subsystem": {
            "never_seen_before": 17,
            "temperatures": [20.1, 20.4],
        },
        "mode": "safe",
        "deployed": True,
    }
    parameters = flatten_parameters(decoded)
    values = {item["path"]: item["value"] for item in parameters}
    assert values["EPS.battery_voltage"] == 4.12
    assert values["new_subsystem.never_seen_before"] == 17
    assert values["new_subsystem.temperatures[1]"] == 20.4
    assert values["mode"] == "safe"
    assert values["deployed"] is True


def test_generic_document_preserves_raw_payload_and_writes_json(tmp_path):
    document = build_generic_telemetry(
        satellite_id="example-sat",
        decoded_data={"unknown_counter": 3},
        source="test",
        decoder="example-decoder",
        raw_payload=b"\x01\x02\x03",
        reception_timestamp_ms=1234567890000,
    )
    target = archive_generic_telemetry(document, tmp_path)
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["raw_payload_hex"] == "010203"
    assert saved["parameters"][0]["name"] == "unknown_counter"
    assert saved["parameters"][0]["metadata_known"] is False


def test_service_stores_and_discovers_new_parameter(monkeypatch, tmp_path):
    monkeypatch.setenv("GENERIC_TELEMETRY_JSON_DIR", str(tmp_path))
    repository = MemoryRepository()
    service = TelemetryService(repository)
    result = service.process_external_decoded(
        {"EPS": {"voltage": 4.1}, "brand_new_field": 99},
        satellite_id="other-sat",
        source="gr_satellites",
        decoder="external-test",
        raw_payload=b"frame",
    )
    assert result["generic_telemetry"]["raw_payload_hex"] == b"frame".hex()
    keys = {item["key"] for item in repository.generic_measurements()}
    assert "external.other-sat.brand_new_field" in keys
    history = repository.history("external.other-sat.brand_new_field")
    assert history[0]["value"] == 99
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_api_accepts_any_decoded_parameter(monkeypatch, tmp_path):
    monkeypatch.setenv("GENERIC_TELEMETRY_JSON_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.post("/ingest/decoded-telemetry", json={
        "satellite_id": "dynamic-sat",
        "parameters": {
            "unplanned_sensor": 123.5,
            "state": "nominal",
        },
        "source": "test",
        "decoder": "test-decoder",
    })
    assert response.status_code == 200
    paths = {
        item["path"]
        for item in response.json()["generic_telemetry"]["parameters"]
    }
    assert {"unplanned_sensor", "state"}.issubset(paths)
    dictionary = client.get("/openmct/dictionary").json()
    keys = {item["key"] for item in dictionary["measurements"]}
    assert "external.dynamic-sat.unplanned_sensor" in keys


def test_invalid_top_level_value_is_rejected():
    try:
        build_generic_telemetry("sat", 123, "test")
    except TypeError as error:
        assert "dictionary or list" in str(error)
    else:
        raise AssertionError("A scalar decoder output must not be accepted")
