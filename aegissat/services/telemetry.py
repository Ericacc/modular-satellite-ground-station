import os
import time

from aegissat.protocol.ax25 import parse_ui_frame
from aegissat.protocol.custom_protocol import TELEMETRY_SIZE, decode_telemetry
from aegissat.protocol.kiss import KISSStreamDecoder, decode_kiss_stream
from aegissat.services.session import ReceptionSession
from aegissat.decoders import decoder_registry
from aegissat.generic_telemetry import (
    archive_generic_telemetry,
    build_generic_telemetry,
)


class TelemetryService:
    def __init__(self, repository):
        self.repository = repository
        self.latest = None
        self.latest_rf = None
        self.received = 0
        self.valid = 0
        self.rejected = 0
        self.session = ReceptionSession()
        self.external_kiss_decoder = KISSStreamDecoder()

    def start_session(self, source, pass_id=None, satellite_id=None):
        return self.session.start(source, pass_id, satellite_id)

    def stop_session(self):
        if self.session.active:
            self.session.stop()
            self.repository.write_session(self.session.to_dict())
        return self.session.to_dict()

    def process_aegissat_simulation(self, payload, pass_id=None):
        return self.process_payload(
            payload,
            source="simulation",
            pass_id=pass_id,
            satellite_id="aegissat-simulation",
            decoder="aegissat-simulated-v1",
        )

    def process_payload(self, payload, source="direct", pass_id=None,
                        satellite_id="aegissat-simulation",
                        decoder="aegissat-simulated-v1"):
        self.received += 1
        if self.session.active:
            self.session.register_frame(len(payload))
        if len(payload) != TELEMETRY_SIZE:
            self.rejected += 1
            if self.session.active:
                self.session.frames_rejected += 1
                self.session.decode_errors += 1
            raise ValueError(
                f"Invalid telemetry payload size: {len(payload)} != {TELEMETRY_SIZE}"
            )
        started = time.perf_counter()
        try:
            telemetry = decode_telemetry(payload)
        except Exception:
            if self.session.active:
                self.session.decode_errors += 1
            raise
        record = {
            "data_source": source,
            "source": source,
            "pass_id": pass_id,
            "satellite_id": satellite_id,
            "decoder": decoder,
            "reception_timestamp_ms": int(time.time() * 1000),
            "processing_latency_ms": (time.perf_counter() - started) * 1000,
            "telemetry": telemetry,
        }
        try:
            self.repository.write(record)
        except Exception:
            if self.session.active:
                self.session.database_errors += 1
            raise
        self.latest = record
        self.valid += 1
        if self.session.active:
            self.session.frames_decoded += 1
        return record

    def process_rf_metrics(self, metrics, pass_id=None, satellite_id=None,
                           data_source="real"):
        record = {
            "data_source": data_source,
            "pass_id": pass_id or self.session.pass_id,
            "satellite_id": satellite_id or self.session.satellite_id,
            "reception_timestamp_ms": int(time.time() * 1000),
            "metrics": metrics,
        }
        self.repository.write_rf(record)
        self.latest_rf = record
        if self.session.active:
            self.session.register_rf(metrics)
        return record

    def process_ax25(self, frame, source="ax25", pass_id=None, has_fcs=True):
        parsed = parse_ui_frame(frame, has_fcs=has_fcs)
        return self.process_payload(parsed["information"], source, pass_id)

    def process_kiss(self, data, source="kiss", pass_id=None, has_fcs=False):
        return [
            self.process_ax25(frame, source, pass_id, has_fcs)
            for frame in decode_kiss_stream(data)
        ]

    def process_external_kiss(self, data, source="gr_satellites", pass_id=None,
                              satellite_id=None, decoder=None):
        records = []
        for frame in self.external_kiss_decoder.feed(data):
            record = {
                "data_source": "real",
                "source": source,
                "pass_id": pass_id or self.session.pass_id,
                "satellite_id": satellite_id or self.session.satellite_id,
                "reception_timestamp_ms": int(time.time() * 1000),
                "frame_size": len(frame),
                "frame_hex": frame.hex(),
                "decoder": decoder or "gr-satellites",
            }
            decoded = decoder_registry.decode(decoder, frame) if decoder else None
            if decoded is not None:
                generic = build_generic_telemetry(
                    satellite_id=record["satellite_id"],
                    decoded_data=decoded,
                    source=source,
                    decoder=record["decoder"],
                    raw_payload=frame,
                    reception_timestamp_ms=record["reception_timestamp_ms"],
                )
                record["generic_telemetry"] = generic
                record["telemetry"] = decoded
                self.repository.write_generic(record)
                self._archive_generic(generic)
                self.latest = record
            self.repository.write_raw_frame(record)
            self.received += 1
            self.valid += 1
            if self.session.active:
                self.session.register_frame(len(frame))
                self.session.frames_decoded += 1
            records.append(record)
        return records

    def process_external_decoded(self, decoded_data, satellite_id="unknown",
                                 source="external_decoder", decoder="external",
                                 pass_id=None, raw_payload=None):
        """Accept fields already identified by an external decoder."""
        self.received += 1
        timestamp_ms = int(time.time() * 1000)
        generic = build_generic_telemetry(
            satellite_id=satellite_id,
            decoded_data=decoded_data,
            source=source,
            decoder=decoder,
            raw_payload=raw_payload,
            reception_timestamp_ms=timestamp_ms,
        )
        record = {
            "kind": "generic_telemetry",
            "data_source": "real",
            "source": source,
            "pass_id": pass_id or self.session.pass_id,
            "satellite_id": satellite_id,
            "decoder": decoder,
            "reception_timestamp_ms": timestamp_ms,
            "generic_telemetry": generic,
        }
        self.repository.write_generic(record)
        archive_path = self._archive_generic(generic)
        if archive_path:
            record["json_file"] = str(archive_path)
        self.latest = record
        self.valid += 1
        if self.session.active:
            self.session.register_frame(
                len(raw_payload) if raw_payload is not None else 0
            )
            self.session.frames_decoded += 1
        return record

    def _archive_generic(self, document):
        directory = os.getenv("GENERIC_TELEMETRY_JSON_DIR", "data/telemetry_json")
        if not directory:
            return None
        return archive_generic_telemetry(document, directory)

    def status(self):
        return {
            "received": self.received,
            "valid": self.valid,
            "rejected": self.rejected,
            "database": self.repository.name,
            "session": self.session.to_dict(),
        }
