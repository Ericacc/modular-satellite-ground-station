import base64
import os
import re
import shutil
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from aegissat.openmct import telemetry_dictionary
from aegissat.orbit import calculate_passes
from aegissat.radio.metrics import calculate_rf_metrics
from aegissat.radio.receiver import ReceiverManager
from aegissat.satellites import get_satellite, load_all_satellites
from aegissat.services.telemetry import TelemetryService
from aegissat.services.scheduler import PassScheduler
from aegissat.services.uplink import UplinkService
from aegissat.simulation import SimulationManager
from aegissat.storage.repository import create_repository
from aegissat.protocol.satellite_command import (
    COMMAND_PING, COMMAND_REQUEST_TELEMETRY, COMMAND_SET_MODE
)

app = FastAPI(title="Modular Satellite Ground Station", version="2.0.0")
cors_origins = [item.strip() for item in os.getenv(
    "CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
).split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

service = TelemetryService(create_repository())
uplink = UplinkService()
receiver = ReceiverManager()
scheduler = PassScheduler(receiver, service)
simulation = SimulationManager(service)


# ------------------------------------------------------------------
# Simulated AegisSat-01 pass used for Open MCT visualisation.
#
# This does not represent an orbital prediction. The first simulated
# pass is placed 20 minutes after API startup. After it finishes,
# another simulated pass is scheduled 95 minutes later.
# ------------------------------------------------------------------

AEGISSAT_DUMMY_PASS_START = (
    datetime.now(timezone.utc)
    + timedelta(minutes=20)
)

AEGISSAT_DUMMY_PASS_DURATION = timedelta(minutes=9)
AEGISSAT_DUMMY_PASS_PERIOD = timedelta(minutes=95)


def _iso_utc(value):
    return value.astimezone(
        timezone.utc
    ).isoformat().replace("+00:00", "Z")


def _aegissat_dummy_pass():
    global AEGISSAT_DUMMY_PASS_START

    now = datetime.now(timezone.utc)

    while (
        AEGISSAT_DUMMY_PASS_START
        + AEGISSAT_DUMMY_PASS_DURATION
        <= now
    ):
        AEGISSAT_DUMMY_PASS_START += (
            AEGISSAT_DUMMY_PASS_PERIOD
        )

    start = AEGISSAT_DUMMY_PASS_START
    end = start + AEGISSAT_DUMMY_PASS_DURATION

    return {
        "available": True,
        "satellite_id": "aegissat-01",
        "satellite_name": "AegisSat-01",
        "kind": "simulated",
        "start": _iso_utc(start),
        "end": _iso_utc(end),
        "maximum_elevation_deg": 55.0,
    }



class BinaryInput(BaseModel):
    data_base64: str
    pass_id: str | None = None
    has_fcs: bool = False


class CommandInput(BaseModel):
    command: str
    parameters: str = ""


class SessionInput(BaseModel):
    source: str = "manual"
    pass_id: str | None = None
    satellite_id: str | None = None


class ReceiverInput(BaseModel):
    satellite_id: str
    pass_id: str | None = None


class RFInput(BaseModel):
    iq_real: list[float]
    iq_imag: list[float]
    sample_rate: float
    center_frequency_hz: float = 0
    pass_id: str | None = None
    satellite_id: str | None = None


class RFMetricsInput(BaseModel):
    signal_power_dbfs: float
    peak_power_dbfs: float
    noise_power_dbfs: float
    snr_db: float
    frequency_peak_hz: float
    frequency_offset_hz: float
    sample_count: int
    pass_id: str | None = None
    satellite_id: str | None = None


class DecodedTelemetryInput(BaseModel):
    satellite_id: str = "unknown"
    parameters: dict | list
    source: str = "external_decoder"
    decoder: str = "external"
    pass_id: str | None = None
    raw_payload_base64: str | None = None


def decode_base64(value):
    try:
        return base64.b64decode(value, validate=True)
    except Exception as error:
        raise HTTPException(status_code=400, detail="Invalid Base64 data") from error


@app.get("/")
def root():
    return {"service": "Modular Satellite Ground Station", "docs": "/docs"}


@app.get("/status")
def status():
    return {
        **service.status(),
        "receiver": receiver.status(),
        "scheduler": scheduler.status(),
        "simulation": simulation.status(),
    }


@app.get("/health")
def health():
    return {
        "api": True,
        "database": service.repository.name,
        "rtl_sdr_available": shutil.which("rtl_test") is not None,
        "gr_satellites_available": shutil.which("gr_satellites") is not None,
        "automatic_catalog": True,
    }


@app.post("/sessions/start")
def start_session(request: SessionInput):
    service.start_session(request.source, request.pass_id, request.satellite_id)
    return service.session.to_dict()


@app.post("/sessions/stop")
def stop_session():
    return service.stop_session()


@app.get("/sessions/current")
def current_session():
    return service.session.to_dict()


@app.get("/satellites")
def satellites():
    try:
        return load_all_satellites()
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/passes/next")
def next_passes(satellite_id: str, hours: float = 24):
    try:
        profile = get_satellite(satellite_id)
        if not profile["norad_id"]:
            raise ValueError("This provisional profile has no NORAD ID")
        return calculate_passes(profile["norad_id"], hours)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/receiver/start")
def start_receiver(request: ReceiverInput):
    try:
        profile = get_satellite(request.satellite_id)
        pass_id = request.pass_id or service.start_session(
            "receiver", satellite_id=request.satellite_id
        )
        return receiver.start(profile, pass_id)
    except (KeyError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/receiver/stop")
def stop_receiver():
    result = receiver.stop()
    if service.session.active:
        service.stop_session()
    return result


@app.get("/receiver/status")
def receiver_status():
    return receiver.status()


@app.post("/scheduler/start")
def start_scheduler():
    try:
        schedule = scheduler.refresh()
        scheduler.start()
        return {"status": scheduler.status(), "passes": schedule[:10]}
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/scheduler/stop")
def stop_scheduler():
    scheduler.stop()
    return scheduler.status()


@app.get("/scheduler/status")
def scheduler_status():
    return scheduler.status()


@app.post("/ingest/rf")
def ingest_rf(request: RFInput):
    if len(request.iq_real) != len(request.iq_imag):
        raise HTTPException(status_code=422, detail="IQ arrays must have equal length")
    samples = [
        complex(real, imag)
        for real, imag in zip(request.iq_real, request.iq_imag)
    ]
    try:
        metrics = calculate_rf_metrics(
            samples, request.sample_rate, request.center_frequency_hz
        )
        return service.process_rf_metrics(
            metrics, request.pass_id, request.satellite_id
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/ingest/rf-metrics")
def ingest_rf_metrics(request: RFMetricsInput):
    values = request.model_dump()
    pass_id = values.pop("pass_id")
    satellite_id = values.pop("satellite_id")
    return service.process_rf_metrics(values, pass_id, satellite_id)


@app.get("/openmct/dictionary")
def openmct_dictionary():
    return telemetry_dictionary(service.repository.generic_measurements())


@app.get("/openmct/realtime")
def openmct_realtime():
    session = service.session.to_dict()
    values = {}
    if service.latest_rf:
        values.update(service.latest_rf["metrics"])
    if service.latest and service.latest.get("telemetry"):
        for section, fields in service.latest["telemetry"].items():
            if not isinstance(fields, dict):
                continue
            for field, value in fields.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    values[f"{section}.{field}"] = value
    if service.latest and service.latest.get("generic_telemetry"):
        document = service.latest["generic_telemetry"]
        satellite = document["satellite"]["id"]
        for parameter in document["parameters"]:
            value = parameter["value"]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values[
                    f"external.{satellite}.{parameter['path']}"
                ] = value
    values.update({
        "frames_received": session["frames_received"],
        "frames_decoded": session["frames_decoded"],
        "frames_rejected": session["frames_rejected"],
    })
    return {
        "timestamp": int(__import__("time").time() * 1000),
        "session": session,
        "receiver": receiver.status(),
        "latest": service.latest,
        "values": values,
    }



@app.get("/openmct/passes")
def openmct_passes(
    external_satellite_id: str = "ao-73",
    hours: float = 24,
):
    """
    Return operational pass information for Open MCT.

    AegisSat-01 uses an explicitly simulated pass because no
    operational orbital elements are currently available.

    The external satellite pass is calculated using the existing
    orbital prediction chain.
    """

    aegissat_pass = _aegissat_dummy_pass()

    try:
        profile = get_satellite(
            external_satellite_id
        )

        norad_id = profile.get("norad_id")

        if not norad_id:
            raise ValueError(
                "Satellite profile has no NORAD ID"
            )

        passes = calculate_passes(
            norad_id,
            hours
        )

        if passes:
            predicted = dict(passes[0])

            external_pass = {
                "available": True,
                "satellite_id":
                    external_satellite_id,
                "satellite_name":
                    profile.get(
                        "name",
                        external_satellite_id,
                    ),
                "kind": "predicted",
                **predicted,
            }
        else:
            external_pass = {
                "available": False,
                "satellite_id":
                    external_satellite_id,
                "satellite_name":
                    profile.get(
                        "name",
                        external_satellite_id,
                    ),
                "kind": "predicted",
                "reason":
                    "No pass found in requested interval",
            }

    except Exception as error:
        external_pass = {
            "available": False,
            "satellite_id":
                external_satellite_id,
            "satellite_name":
                external_satellite_id,
            "kind": "predicted",
            "error": str(error),
        }

    return {
        "timestamp": int(
            datetime.now(
                timezone.utc
            ).timestamp() * 1000
        ),
        "aegissat": aegissat_pass,
        "external": external_pass,
    }


@app.get("/openmct/history")
def openmct_history(key: str, start: int | None = None, end: int | None = None):
    if not re.fullmatch(r"[A-Za-z0-9_.+\[\]-]+", key):
        raise HTTPException(status_code=422, detail="Invalid telemetry key")

    session_keys = {
        "frames_received",
        "frames_decoded",
        "frames_rejected",
    }

    if key in session_keys:
        session = service.session.to_dict()
        timestamp = int(__import__("time").time() * 1000)

        if start is not None and timestamp < start:
            return []

        if end is not None and timestamp > end:
            return []

        return [
            {
                "timestamp": timestamp,
                "value": session[key],
            }
        ]

    return service.repository.history(key, start, end)


@app.get("/telemetry/latest")
def latest():
    if service.latest is None:
        raise HTTPException(status_code=404, detail="No telemetry received")
    return service.latest


@app.post("/simulation/start")
def start_simulation():
    return simulation.start()


@app.post("/simulation/stop")
def stop_simulation():
    return simulation.stop()


@app.get("/simulation/status")
def simulation_status():
    return simulation.status()


@app.post("/ingest/payload")
def ingest_payload(request: BinaryInput):
    try:
        return service.process_aegissat_simulation(
            decode_base64(request.data_base64), request.pass_id
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/ingest/ax25")
def ingest_ax25(request: BinaryInput):
    try:
        return service.process_ax25(
            decode_base64(request.data_base64),
            "api_ax25",
            request.pass_id,
            request.has_fcs,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/ingest/kiss")
def ingest_kiss(request: BinaryInput):
    try:
        return service.process_kiss(
            decode_base64(request.data_base64),
            "api_kiss",
            request.pass_id,
            request.has_fcs,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/ingest/external-kiss")
def ingest_external_kiss(request: BinaryInput):
    return service.process_external_kiss(
        decode_base64(request.data_base64), pass_id=request.pass_id
    )


@app.post("/ingest/decoded-telemetry")
def ingest_decoded_telemetry(request: DecodedTelemetryInput):
    raw_payload = None
    if request.raw_payload_base64:
        raw_payload = decode_base64(request.raw_payload_base64)
    try:
        return service.process_external_decoded(
            decoded_data=request.parameters,
            satellite_id=request.satellite_id,
            source=request.source,
            decoder=request.decoder,
            pass_id=request.pass_id,
            raw_payload=raw_payload,
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/satellite/commands")
def satellite_command(request: CommandInput):
    command_ids = {
        "ping": COMMAND_PING,
        "request_telemetry": COMMAND_REQUEST_TELEMETRY,
        "set_mode": COMMAND_SET_MODE,
    }
    command_id = command_ids.get(request.command)
    if command_id is None:
        raise HTTPException(status_code=422, detail="Unsupported satellite command")
    return uplink.queue_command(command_id, request.parameters.encode("utf-8"))
