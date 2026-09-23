import os
import shlex
import subprocess
import threading
import time
from pathlib import Path

from aegissat.config import PROJECT_ROOT
import sys


class ReceiverManager:
    def __init__(self):
        self.process = None
        self.profile_id = None
        self.pass_id = None
        self.last_error = None
        self._lock = threading.Lock()

    def start(self, profile, pass_id):
        with self._lock:
            if self.process and self.process.poll() is None:
                raise RuntimeError("Receiver is already running")
            values = {
                "frequency_hz": profile["downlink_frequency_hz"],
                "sample_rate": profile.get("sample_rate", 240000),
                "baud_rate": profile.get("baud_rate", 9600),
                "satellite_id": profile["id"],
                "pass_id": pass_id,
                "gr_satellites_id": profile.get("gr_satellites_id", profile.get("norad_id")),
                "norad_id": profile.get("norad_id") or 0,
                "rtl_sample_rate": profile.get("rtl_sample_rate", 240000),
                "decoder": profile.get("decoder", "iq_recording"),
                "python": sys.executable,
            }
            template = os.getenv(
                "RECEIVER_COMMAND",
                "{python} scripts/real_receiver.py --decoder {decoder} "
                "--satellite {gr_satellites_id} --norad-id {norad_id} "
                "--frequency {frequency_hz} "
                "--rtl-sample-rate {rtl_sample_rate} --pass-id {pass_id}",
            )
            command = shlex.split(template.format(**values))
            log_dir = Path(os.getenv("LOG_DIR", PROJECT_ROOT / "logs"))
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"receiver-{pass_id}.log"
            self.log_file = open(log_path, "ab", buffering=0)
            self.process = subprocess.Popen(
                command,
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=PROJECT_ROOT,
            )
            time.sleep(0.25)
            if self.process.poll() is not None:
                self.log_file.close()
                raise RuntimeError(
                    f"Receiver exited during startup; inspect {log_path}"
                )
            self.profile_id = profile["id"]
            self.pass_id = pass_id
            self.last_error = None
            return self.status()

    def stop(self):
        with self._lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            if getattr(self, "log_file", None):
                self.log_file.close()
                self.log_file = None
            return self.status()

    def status(self):
        running = self.process is not None and self.process.poll() is None
        return {
            "running": running,
            "pid": self.process.pid if running else None,
            "profile_id": self.profile_id,
            "pass_id": self.pass_id,
            "return_code": None if not self.process else self.process.poll(),
            "last_error": self.last_error,
        }
