import math
import random
import threading
import time

from aegissat.protocol.custom_protocol import encode_telemetry


def simulated_telemetry(counter, elapsed_seconds):
    wave = math.sin(elapsed_seconds / 18.0)
    return {
        "header": {
            "id_sat": 1,
            "timestamp_ms": int(time.time() * 1000),
            "time_alive": int(elapsed_seconds),
            "counter_packs": counter,
        },
        "eps": {
            "vbat": 7.4 + 0.25 * wave,
            "ibat": 0.45 + 0.08 * math.cos(elapsed_seconds / 13.0),
            "tbat": 26.0 + wave,
            "vsolar1": 8.2 + 0.6 * max(0, wave),
            "isolar1": 0.22,
            "vsolar2": 8.0 + 0.5 * max(0, wave),
            "isolar2": 0.20,
            "teps": 28.0 + wave,
        },
        "adcs": {
            "tadcs": 27.0 + wave,
            "w_x": 0.02 * wave,
            "w_y": 0.02 * math.cos(elapsed_seconds / 15.0),
            "w_z": 0.01 * math.sin(elapsed_seconds / 11.0),
            "mag_x": 10.0,
            "mag_y": 11.0,
            "mag_z": 12.0,
            "sun_x": 0.1,
            "sun_y": 0.2,
            "sun_z": 0.3,
        },
        "obc": {
            "tobc": 31.0 + 2.0 * wave,
            "cpu_ocuppation": 40,
            "ram_free": 1024,
            "flash_memory_ocuppation": 2048,
        },
        "comms": {
            "tx_power": 2.0,
            "rx_RSSI": -70.0,
            "rx_snr": 12.0,
            "message_error_rate": 0.01,
            "ber": 0.001,
        },
        "payload": {"tpayload": 28.0 + wave, "ipayload": 0.15, "payload_state": 1},
        "weather": {"external_temp": 24.0, "solar_reception": 850.0},
        "orbit": {
            "orbit_ID": 1,
            "orbit_height": 500.0,
            "orbit_latitude": 0.0 + wave,
            "orbit_longitude": 0.0,
        },
        "flags": {"error_flag": 0, "start_flag": 1, "end_flag": 1},
    }


class SimulationManager:
    def __init__(self, telemetry_service, interval_seconds=1.0):
        self.service = telemetry_service
        self.interval_seconds = interval_seconds
        self.thread = None
        self.stop_event = threading.Event()
        self.counter = 0
        self.started_at = None
        self.last_error = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return self.status()
        self.stop_event.clear()
        self.counter = 0
        self.started_at = time.time()
        self.last_error = None
        self.service.start_session("simulation", satellite_id="aegissat-simulation")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self.status()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                telemetry = simulated_telemetry(
                    self.counter, time.time() - self.started_at
                )
                payload = encode_telemetry(telemetry)
                self.service.process_aegissat_simulation(payload)
                self.service.process_rf_metrics(
                    {
                        "signal_power_dbfs": -28.0 + random.uniform(-1.0, 1.0),
                        "snr_db": 12.0 + random.uniform(-0.8, 0.8),
                        "frequency_offset_hz": random.uniform(-25.0, 25.0),
                    },
                    satellite_id="aegissat-simulation",
                    data_source="simulation",
                )
                self.counter += 1
            except Exception as error:
                self.last_error = str(error)
                self.stop_event.set()
                break
            self.stop_event.wait(self.interval_seconds)

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        if self.service.session.active and self.service.session.source == "simulation":
            self.service.stop_session()
        return self.status()

    def status(self):
        return {
            "running": bool(self.thread and self.thread.is_alive()),
            "generated_frames": self.counter,
            "started_at": self.started_at,
            "last_error": self.last_error,
        }
