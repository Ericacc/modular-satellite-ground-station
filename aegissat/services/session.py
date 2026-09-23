from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_pass_id(source):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{source}_{timestamp}"


@dataclass
class ReceptionSession:
    active: bool = False
    source: str | None = None
    pass_id: str | None = None
    satellite_id: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    last_frame_at: str | None = None
    frames_received: int = 0
    frames_decoded: int = 0
    frames_rejected: int = 0
    decode_errors: int = 0
    database_errors: int = 0
    bytes_received: int = 0
    rf_measurements: int = 0
    snr_sum_db: float = 0.0
    maximum_snr_db: float | None = None
    power_sum_dbfs: float = 0.0

    def start(self, source, pass_id=None, satellite_id=None):
        self.__dict__.update(ReceptionSession().__dict__)
        self.active = True
        self.source = source
        self.pass_id = pass_id or make_pass_id(source)
        self.satellite_id = satellite_id
        self.started_at = utc_now()
        return self.pass_id

    def stop(self):
        self.active = False
        self.ended_at = utc_now()

    def register_frame(self, size):
        self.frames_received += 1
        self.bytes_received += size
        self.last_frame_at = utc_now()

    def register_rf(self, metrics):
        self.rf_measurements += 1
        self.snr_sum_db += metrics["snr_db"]
        self.power_sum_dbfs += metrics["signal_power_dbfs"]
        if self.maximum_snr_db is None:
            self.maximum_snr_db = metrics["snr_db"]
        else:
            self.maximum_snr_db = max(self.maximum_snr_db, metrics["snr_db"])

    def to_dict(self):
        result = asdict(self)
        count = self.rf_measurements
        result["average_snr_db"] = self.snr_sum_db / count if count else None
        result["average_power_dbfs"] = self.power_sum_dbfs / count if count else None
        result.pop("snr_sum_db")
        result.pop("power_sum_dbfs")
        return result

