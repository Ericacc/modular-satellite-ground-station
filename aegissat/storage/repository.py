import os
from datetime import datetime, timezone

from aegissat import config  # Loads .env before repository selection.


class MemoryRepository:
    name = "memory"

    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(record)

    def write_rf(self, record):
        self.records.append({"kind": "rf_measurement", **record})

    def write_session(self, record):
        self.records.append({"kind": "pass_summary", **record})

    def write_raw_frame(self, record):
        self.records.append({"kind": "raw_frame", **record})

    def write_generic(self, record):
        self.records.append({"kind": "generic_telemetry", **record})

    def generic_measurements(self):
        measurements = {}
        for item in self.records:
            document = item.get("generic_telemetry")
            if not document:
                continue
            satellite = document["satellite"]["id"]
            for parameter in document["parameters"]:
                key = f"external.{satellite}.{parameter['path']}"
                measurements[key] = {
                    "key": key,
                    "name": f"{satellite}: {parameter['path']}",
                    "units": parameter.get("unit") or "",
                }
        return sorted(measurements.values(), key=lambda item: item["key"])

    def history(self, key=None, start_ms=None, end_ms=None):
        output = []
        for item in self.records:
            timestamp = item.get("reception_timestamp_ms")
            if timestamp is None:
                continue
            if start_ms is not None and timestamp < start_ms:
                continue
            if end_ms is not None and timestamp > end_ms:
                continue
            if item.get("kind") == "rf_measurement" and key in item.get("metrics", {}):
                output.append({"timestamp": timestamp, "value": item["metrics"][key]})
            elif "telemetry" in item and key and "." in key:
                section, field = key.split(".", 1)
                value = item["telemetry"].get(section, {}).get(field)
                if isinstance(value, (int, float)):
                    output.append({"timestamp": timestamp, "value": value})
            elif item.get("generic_telemetry") and key and key.startswith("external."):
                document = item["generic_telemetry"]
                satellite = document["satellite"]["id"]
                prefix = f"external.{satellite}."
                if not key.startswith(prefix):
                    continue
                wanted_path = key[len(prefix):]
                for parameter in document["parameters"]:
                    if parameter["path"] == wanted_path:
                        value = parameter["value"]
                        if isinstance(value, (int, float, str, bool)):
                            output.append({"timestamp": timestamp, "value": value})
        return output


class InfluxRepository:
    name = "influxdb"

    def __init__(self):
        from influxdb_client import InfluxDBClient, Point
        self.Point = Point
        self.client = InfluxDBClient(
            url=os.environ["INFLUX_URL"],
            token=os.environ["INFLUX_TOKEN"],
            org=os.environ["INFLUX_ORG"],
        )
        self.bucket = os.environ["INFLUX_BUCKET"]
        self.org = os.environ["INFLUX_ORG"]
        from influxdb_client.client.write_api import SYNCHRONOUS
        self.writer = self.client.write_api(write_options=SYNCHRONOUS)

    def _timestamp(self):
        return datetime.now(timezone.utc)

    def write(self, record):
        points = []
        telemetry = record["telemetry"]
        for subsystem, fields in telemetry.items():
            if not isinstance(fields, dict):
                continue
            for parameter, value in fields.items():
                if isinstance(value, bool):
                    value = float(value)
                elif isinstance(value, (int, float)):
                    value = float(value)
                elif not isinstance(value, str):
                    continue
                point = (
                    self.Point("telemetry")
                    .tag("source", record["source"])
                    .tag("pass_id", record["pass_id"] or "unknown")
                    .tag("subsystem", subsystem)
                    .tag("parameter", parameter)
                    .field("value", value)
                    .time(self._timestamp())
                )
                points.append(point)
        packet = (
            self.Point("telemetry_packet")
            .tag("source", record["source"])
            .tag("pass_id", record["pass_id"] or "unknown")
            .field("processing_latency_ms", record["processing_latency_ms"])
            .time(self._timestamp())
        )
        points.append(packet)
        self.writer.write(bucket=self.bucket, org=self.org, record=points)

    def write_rf(self, record):
        record = {"reception_timestamp_ms": int(self._timestamp().timestamp() * 1000), **record}
        point = (
            self.Point("rf_measurement")
            .tag("pass_id", record.get("pass_id") or "unknown")
            .tag("satellite_id", record.get("satellite_id") or "unknown")
            .time(self._timestamp())
        )
        for name, value in record["metrics"].items():
            if isinstance(value, (int, float)):
                point = point.field(name, value)
        self.writer.write(bucket=self.bucket, org=self.org, record=point)

    def write_session(self, record):
        point = (
            self.Point("pass_summary")
            .tag("pass_id", record.get("pass_id") or "unknown")
            .tag("satellite_id", record.get("satellite_id") or "unknown")
            .tag("source", record.get("source") or "unknown")
            .time(self._timestamp())
        )
        for name, value in record.items():
            if name in {"pass_id", "satellite_id", "source"} or value is None:
                continue
            if isinstance(value, (bool, int, float, str)):
                point = point.field(name, value)
        self.writer.write(bucket=self.bucket, org=self.org, record=point)

    def write_raw_frame(self, record):
        point = (
            self.Point("raw_frame")
            .tag("pass_id", record.get("pass_id") or "unknown")
            .tag("satellite_id", record.get("satellite_id") or "unknown")
            .tag("source", record.get("source") or "unknown")
            .field("frame_hex", record["frame_hex"])
            .field("frame_size", record["frame_size"])
            .time(self._timestamp())
        )
        self.writer.write(bucket=self.bucket, org=self.org, record=point)

    def write_generic(self, record):
        document = record["generic_telemetry"]
        satellite = document["satellite"]["id"]
        points = []
        for parameter in document["parameters"]:
            value = parameter["value"]
            point = (
                self.Point("generic_telemetry")
                .tag("satellite_id", satellite)
                .tag("parameter_path", parameter["path"])
                .tag("parameter_name", parameter["name"])
                .tag("unit", parameter.get("unit") or "")
                .time(datetime.fromtimestamp(
                    document["reception"]["timestamp_ms"] / 1000,
                    timezone.utc,
                ))
            )
            if isinstance(value, bool):
                point = point.field("value_boolean", value)
            elif isinstance(value, (int, float)):
                point = point.field("value_number", float(value))
            elif value is not None:
                point = point.field("value_text", str(value))
            else:
                continue
            points.append(point)
        if points:
            self.writer.write(bucket=self.bucket, org=self.org, record=points)

    def generic_measurements(self):
        query = (
            f'from(bucket: "{self.bucket}") |> range(start: -30d) '
            '|> filter(fn: (r) => r._measurement == "generic_telemetry") '
            '|> keep(columns: ["satellite_id", "parameter_path", '
            '"parameter_name", "unit"]) |> distinct(column: "parameter_path")'
        )
        tables = self.client.query_api().query(query, org=self.org)
        measurements = {}
        for table in tables:
            for item in table.records:
                values = item.values
                satellite = values.get("satellite_id", "unknown")
                path = values.get("parameter_path")
                if not path:
                    continue
                key = f"external.{satellite}.{path}"
                measurements[key] = {
                    "key": key,
                    "name": f"{satellite}: {path}",
                    "units": values.get("unit") or "",
                }
        return sorted(measurements.values(), key=lambda item: item["key"])

    def history(self, key=None, start_ms=None, end_ms=None):
        if not key:
            return []
        start = f"time(v: {int(start_ms) * 1_000_000})" if start_ms is not None else "-24h"
        stop = f"time(v: {int(end_ms) * 1_000_000})" if end_ms is not None else "now()"
        if key.startswith("external."):
            parts = key.split(".", 2)
            if len(parts) != 3:
                return []
            satellite, parameter = parts[1], parts[2]
            filters = (
                'r._measurement == "generic_telemetry" and '
                f'r.satellite_id == "{satellite}" and '
                f'r.parameter_path == "{parameter}"'
            )
        elif "." in key:
            subsystem, parameter = key.split(".", 1)
            filters = (
                'r._measurement == "telemetry" and '
                f'r.subsystem == "{subsystem}" and r.parameter == "{parameter}"'
            )
        else:
            filters = f'r._measurement == "rf_measurement" and r._field == "{key}"'
        query = (
            f'from(bucket: "{self.bucket}") |> range(start: {start}, stop: {stop}) '
            f'|> filter(fn: (r) => {filters})'
        )
        tables = self.client.query_api().query(query, org=self.org)
        output = []
        for table in tables:
            for record in table.records:
                output.append({
                    "timestamp": int(record.get_time().timestamp() * 1000),
                    "value": record.get_value(),
                })
        return output


def create_repository():
    if os.getenv("STORAGE_BACKEND", "memory").lower() == "influxdb":
        return InfluxRepository()
    return MemoryRepository()
