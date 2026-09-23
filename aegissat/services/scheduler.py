import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aegissat.orbit import calculate_passes
from aegissat.satellites import load_all_satellites


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGETS_PATH = PROJECT_ROOT / "config" / "reception_targets.json"


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_reception_target_ids(path=TARGETS_PATH):
    """Load the enabled NORAD IDs selected for automatic reception."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Reception targets file was not found: {path}"
        )

    document = json.loads(path.read_text(encoding="utf-8"))
    targets = document.get("targets")

    if not isinstance(targets, list):
        raise ValueError(
            "reception_targets.json must contain a 'targets' list"
        )

    enabled_ids = set()

    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            raise ValueError(
                f"Target at position {index} must be an object"
            )

        if not target.get("enabled", True):
            continue

        norad_id = target.get("norad_id")

        if norad_id is None:
            raise ValueError(
                f"Enabled target at position {index} has no norad_id"
            )

        try:
            norad_id = int(norad_id)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid norad_id at position {index}: {norad_id}"
            ) from error

        if norad_id <= 0:
            raise ValueError(
                f"norad_id must be positive at position {index}"
            )

        enabled_ids.add(norad_id)

    return enabled_ids


def select_non_overlapping_passes(schedule):
    """Select the highest pass when reception windows overlap."""

    start_margin = int(
        os.getenv("RECEIVER_START_MARGIN_SECONDS", "120")
    )
    stop_margin = int(
        os.getenv("RECEIVER_STOP_MARGIN_SECONDS", "60")
    )

    ranked = sorted(
        schedule,
        key=lambda item: float(
            item.get("maximum_elevation_deg") or -90.0
        ),
        reverse=True,
    )

    selected = []

    for candidate in ranked:
        candidate_start = (
            parse_time(candidate["start"])
            - timedelta(seconds=start_margin)
        )
        candidate_end = (
            parse_time(candidate["end"])
            + timedelta(seconds=stop_margin)
        )

        overlaps = False

        for existing in selected:
            existing_start = (
                parse_time(existing["start"])
                - timedelta(seconds=start_margin)
            )
            existing_end = (
                parse_time(existing["end"])
                + timedelta(seconds=stop_margin)
            )

            if (
                candidate_start <= existing_end
                and candidate_end >= existing_start
            ):
                overlaps = True
                break

        if not overlaps:
            selected.append(candidate)

    return sorted(
        selected,
        key=lambda item: item["start"],
    )


class PassScheduler:
    def __init__(
        self,
        receiver,
        telemetry_service,
        poll_seconds=30,
    ):
        self.receiver = receiver
        self.telemetry_service = telemetry_service
        self.poll_seconds = poll_seconds
        self.running = False
        self.thread = None
        self.schedule = []
        self.last_error = None

    def refresh(self):
        schedule = []
        target_ids = load_reception_target_ids()

        for profile in load_all_satellites():
            norad_id = profile.get("norad_id")

            if (
                not profile.get("enabled", True)
                or not norad_id
                or profile.get("decoder") == "laboratory"
            ):
                continue

            try:
                norad_id = int(norad_id)
            except (TypeError, ValueError):
                continue

            if norad_id not in target_ids:
                continue

            try:
                satellite_passes = calculate_passes(
                    norad_id,
                    hours=24,
                )

                for satellite_pass in satellite_passes:
                    schedule.append(
                        {
                            "profile": profile,
                            **satellite_pass,
                        }
                    )
            except (KeyError, ValueError, OSError):
                continue

        self.schedule = select_non_overlapping_passes(
            schedule
        )
        self.last_error = None
        return self.schedule

    def tick(self, now=None):
        now = now or datetime.now(timezone.utc)

        for item in self.schedule:
            start = parse_time(item["start"])
            end = parse_time(item["end"])
            profile = item["profile"]

            pass_id = (
                f"{profile['id']}_"
                f"{start.strftime('%Y%m%dT%H%M%SZ')}"
            )

            status = self.receiver.status()

            start_margin = int(
                os.getenv(
                    "RECEIVER_START_MARGIN_SECONDS",
                    "120",
                )
            )
            stop_margin = int(
                os.getenv(
                    "RECEIVER_STOP_MARGIN_SECONDS",
                    "60",
                )
            )

            if (
                now > end + timedelta(seconds=stop_margin)
                and status["running"]
                and status["pass_id"] == pass_id
            ):
                result = self.receiver.stop()

                if self.telemetry_service.session.active:
                    self.telemetry_service.stop_session()

                return result

            if (
                start - timedelta(seconds=start_margin)
                <= now
                <= end
                and not status["running"]
            ):
                self.telemetry_service.start_session(
                    "scheduled",
                    pass_id,
                    profile["id"],
                )

                return self.receiver.start(
                    profile,
                    pass_id,
                )

        return self.receiver.status()

    def _loop(self):
        while self.running:
            try:
                now = datetime.now(timezone.utc)

                if (
                    not self.schedule
                    or all(
                        parse_time(item["end"]) < now
                        for item in self.schedule
                    )
                ):
                    self.refresh()

                self.tick(now)

            except Exception as error:
                self.last_error = str(error)

            time.sleep(self.poll_seconds)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(
                target=self._loop,
                daemon=True,
            )
            self.thread.start()

    def stop(self):
        self.running = False

        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None

    def status(self):
        return {
            "running": self.running,
            "scheduled_passes": len(self.schedule),
            "next_pass": (
                self.schedule[0]
                if self.schedule
                else None
            ),
            "last_error": self.last_error,
        }
