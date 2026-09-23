import socket
import time

import pytest
from fastapi.testclient import TestClient

from aegissat.api import app
from aegissat.protocol.ax25 import build_ui_frame, parse_ui_frame
from aegissat.protocol.custom_protocol import (
    TELEMETRY_SIZE, decode_telemetry, encode_telemetry
)
from aegissat.protocol.ipc import TYPE_TELEMETRY, encode_message, extract_messages
from aegissat.protocol.kiss import decode_kiss_stream, encode_kiss_frame
from aegissat.protocol.kiss import KISSStreamDecoder
from aegissat.orbit import load_tle_by_norad
from aegissat.radio.fec import convolutional_encode, viterbi_decode
from aegissat.radio.metrics import calculate_rf_metrics
from aegissat.catalog import discover_satellites
from aegissat.satellites import load_satellites
from aegissat.services.scheduler import PassScheduler
from aegissat.services.telemetry import TelemetryService
from aegissat.services.uplink import UplinkService
from aegissat.protocol.satellite_command import COMMAND_PING, decode_command
from aegissat.radio.config import load_gmsk_config, validate_gmsk_config
from aegissat.radio.hdlc import decode_hdlc_frames, encode_hdlc_frame
from aegissat.storage.repository import MemoryRepository
from aegissat.transport.tcp_server import TelemetryTCPServer
from aegissat.decoders import DecoderRegistry
from aegissat.openmct import telemetry_dictionary
from aegissat.simulation import SimulationManager
from tests.sample_data import sample_telemetry


def test_custom_protocol_round_trip():
    payload = encode_telemetry(sample_telemetry())
    assert len(payload) == TELEMETRY_SIZE == 167
    assert decode_telemetry(payload)["header"]["id_sat"] == 1
    with pytest.raises(ValueError):
        decode_telemetry(payload[:-1])


def test_ax25_and_kiss_round_trip():
    payload = encode_telemetry(sample_telemetry())
    frame = build_ui_frame("GROUND", "AEGIS", payload)
    parsed = parse_ui_frame(frame)
    assert parsed["information"] == payload
    kiss = encode_kiss_frame(frame)
    assert decode_kiss_stream(kiss) == [frame]
    corrupted = bytearray(frame)
    corrupted[20] ^= 1
    with pytest.raises(ValueError):
        parse_ui_frame(bytes(corrupted))


def test_ipc_fragmentation():
    payload = encode_telemetry(sample_telemetry())
    first = encode_message(TYPE_TELEMETRY, 1, payload)
    second = encode_message(TYPE_TELEMETRY, 2, payload)
    messages, remaining = extract_messages(first[:5])
    assert messages == []
    messages, remaining = extract_messages(remaining + first[5:] + second)
    assert [message["sequence"] for message in messages] == [1, 2]
    assert remaining == b""


def test_service_sources_are_equivalent():
    repository = MemoryRepository()
    service = TelemetryService(repository)
    payload = encode_telemetry(sample_telemetry())
    frame = build_ui_frame("GROUND", "AEGIS", payload, include_fcs=False)
    direct = service.process_payload(payload)["telemetry"]
    ax25 = service.process_ax25(frame, has_fcs=False)["telemetry"]
    kiss = service.process_kiss(
        encode_kiss_frame(frame), has_fcs=False
    )[0]["telemetry"]
    assert direct == ax25 == kiss


def test_tcp_end_to_end():
    repository = MemoryRepository()
    service = TelemetryService(repository)
    server = TelemetryTCPServer(service, port=0)
    server.start()
    payload = encode_telemetry(sample_telemetry(42))
    message = encode_message(TYPE_TELEMETRY, 42, payload)
    with socket.create_connection(server.address, timeout=2) as client:
        client.sendall(message[:7])
        client.sendall(message[7:])
    for _ in range(20):
        if repository.records:
            break
        time.sleep(0.01)
    server.stop()
    assert repository.records[0]["telemetry"]["header"]["counter_packs"] == 42


def test_api():
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/status").status_code == 200
    assert client.get("/openmct/dictionary").status_code == 200
    assert client.get("/openmct/history", params={"key": "snr_db"}).status_code == 200
    assert client.get("/openmct/history", params={"key": 'bad"key'}).status_code == 422


def test_uplink_queue(tmp_path):
    service = UplinkService(tmp_path / "commands.kiss")
    result = service.queue_command(COMMAND_PING)
    kiss_frames = decode_kiss_stream((tmp_path / "commands.kiss").read_bytes())
    ax25 = parse_ui_frame(kiss_frames[0], has_fcs=False)
    command = decode_command(ax25["information"])
    assert result["status"] == "queued"
    assert command["command_id"] == COMMAND_PING


def test_gmsk_configuration_and_hdlc_round_trip():
    config = load_gmsk_config()
    validate_gmsk_config(config)
    assert config.profile == "laboratory_default"
    assert config.sample_rate == config.symbol_rate * config.samples_per_symbol

    payload = encode_telemetry(sample_telemetry())
    frame = build_ui_frame("GROUND", "AEGIS", payload)
    recovered = decode_hdlc_frames(encode_hdlc_frame(frame))
    assert frame in recovered
    assert parse_ui_frame(frame)["information"] == payload


def test_kiss_incremental_stream():
    payload = encode_telemetry(sample_telemetry())
    frame = build_ui_frame("GROUND", "AEGIS", payload)
    encoded = encode_kiss_frame(frame)
    decoder = KISSStreamDecoder()
    assert decoder.feed(encoded[:20]) == []
    assert decoder.feed(encoded[20:]) == [frame]
    assert decoder.finish() is False


def test_reception_session_and_rf_metrics():
    repository = MemoryRepository()
    service = TelemetryService(repository)
    service.start_session("test", "pass-001", "aegissat")
    payload = encode_telemetry(sample_telemetry())
    service.process_payload(payload, pass_id="pass-001")
    metrics = {
        "signal_power_dbfs": -20.0,
        "snr_db": 8.0,
    }
    service.process_rf_metrics(metrics)
    summary = service.stop_session()
    assert summary["frames_received"] == 1
    assert summary["frames_decoded"] == 1
    assert summary["average_snr_db"] == 8.0


def test_fec_corrects_single_hard_decision_error():
    bits = [1, 0, 1, 1, 0, 0, 1, 0]
    encoded = convolutional_encode(bits)
    encoded[5] ^= 1
    result = viterbi_decode(encoded)
    assert result["bits"] == bits
    assert result["corrected_metric"] == 1


def test_rf_metrics_detect_tone():
    import numpy as np

    sample_rate = 48000
    count = 4096
    frequency = 3000
    index = np.arange(count)
    rng = np.random.default_rng(7)
    samples = np.exp(2j * np.pi * frequency * index / sample_rate)
    samples += 0.05 * (rng.normal(size=count) + 1j * rng.normal(size=count))
    metrics = calculate_rf_metrics(samples, sample_rate, 437_000_000)
    assert abs(metrics["frequency_offset_hz"] - frequency) < sample_rate / count
    assert metrics["snr_db"] > 10


def test_satellite_profiles_load():
    profiles = load_satellites()
    assert profiles[0]["id"] == "aegissat-01-laboratory"
    assert profiles[0]["provisional"] is True
    profile_ids = {
        profile["id"]
        for profile in profiles
    }

    assert "aegissat-01-laboratory" in profile_ids
    assert "ao-73" in profile_ids

    ao73 = next(
        profile
        for profile in profiles
        if profile["id"] == "ao-73"
    )

    assert ao73["norad_id"] == 39444
    assert ao73["downlink_frequency_hz"] == 145935000


def test_automatic_catalog_filters_active_supported_band(tmp_path):
    cache = tmp_path / "transmitters.json"
    cache.write_text(__import__("json").dumps([
        {
            "norad_cat_id": 12345,
            "downlink_low": 437500000,
            "status": "active",
            "mode": "GMSK",
            "baud": 9600,
            "uuid": "example",
        },
        {
            "norad_cat_id": 54321,
            "downlink_low": 2400000000,
            "status": "active",
        },
    ]), encoding="utf-8")
    profiles = discover_satellites(cache)
    assert [profile["norad_id"] for profile in profiles] == [12345]
    assert profiles[0]["decoder"] == "iq_recording"


def test_external_kiss_is_stored_without_aegissat_decoding():
    repository = MemoryRepository()
    service = TelemetryService(repository)
    service.start_session("gr_satellites", "real-001", "ao-73")
    encoded = encode_kiss_frame(b"external satellite frame")
    assert service.process_external_kiss(encoded[:7]) == []
    records = service.process_external_kiss(encoded[7:])
    assert records[0]["frame_hex"] == b"external satellite frame".hex()
    assert repository.records[-1]["kind"] == "raw_frame"


def test_tle_lookup_by_norad_uses_cached_three_line_data(tmp_path):
    cache = tmp_path / "tle.txt"
    cache.write_text(
        "ISS (ZARYA)\n"
        "1 25544U 98067A   24200.00000000  .00000000  00000-0  00000-0 0  9999\n"
        "2 25544  51.6400 100.0000 0005000 100.0000 260.0000 15.50000000123456\n",
        encoding="utf-8",
    )
    name, line1, line2 = load_tle_by_norad(25544, cache)
    assert name == "ISS (ZARYA)"
    assert line1.startswith("1 25544")


def test_scheduler_starts_and_stops_simulated_pass(monkeypatch):
    from datetime import datetime, timedelta, timezone

    class FakeReceiver:
        def __init__(self):
            self.running = False
            self.pass_id = None

        def status(self):
            return {"running": self.running, "pass_id": self.pass_id}

        def start(self, profile, pass_id):
            self.running = True
            self.pass_id = pass_id
            return self.status()

        def stop(self):
            self.running = False
            return self.status()

    repository = MemoryRepository()
    service = TelemetryService(repository)
    receiver = FakeReceiver()
    scheduler = PassScheduler(receiver, service)
    monkeypatch.setenv("RECEIVER_STOP_MARGIN_SECONDS", "0")
    now = datetime.now(timezone.utc)
    scheduler.schedule = [{
        "profile": {"id": "test-satellite"},
        "start": (now - timedelta(seconds=5)).isoformat(),
        "maximum": now.isoformat(),
        "end": (now + timedelta(seconds=5)).isoformat(),
    }]
    scheduler.tick(now)
    assert receiver.running is True
    assert service.session.active is True
    scheduler.tick(now + timedelta(seconds=10))
    assert receiver.running is False
    assert service.session.active is False


def test_optional_decoder_registry_does_not_require_satellite_logic():
    registry = DecoderRegistry()
    assert registry.decode("missing", b"frame") is None
    registry.register("example", lambda frame: {"payload": {"length": len(frame)}})
    assert registry.decode("example", b"1234") == {"payload": {"length": 4}}


def test_simulation_uses_the_normal_ingest_and_storage_chain():
    repository = MemoryRepository()
    service = TelemetryService(repository)
    simulation = SimulationManager(service, interval_seconds=0.01)
    simulation.start()
    for _ in range(50):
        if simulation.counter >= 2:
            break
        time.sleep(0.01)
    result = simulation.stop()
    telemetry_records = [item for item in repository.records if "telemetry" in item]
    assert result["running"] is False
    assert telemetry_records
    assert telemetry_records[0]["data_source"] == "simulation"
    assert telemetry_records[0]["satellite_id"] == "aegissat-simulation"
    assert telemetry_records[0]["decoder"] == "aegissat-simulated-v1"


def test_openmct_dictionary_separates_rf_and_simulated_values():
    keys = {item["key"] for item in telemetry_dictionary()["measurements"]}
    assert {"snr_db", "eps.vbat", "obc.tobc"}.issubset(keys)
