SIMULATED_MEASUREMENTS = [
    {"key": "eps.vbat", "name": "Battery voltage (simulated)", "units": "V"},
    {"key": "eps.ibat", "name": "Battery current (simulated)", "units": "A"},
    {"key": "eps.vsolar1", "name": "Solar voltage 1 (simulated)", "units": "V"},
    {"key": "payload.tpayload", "name": "Payload temperature (simulated)", "units": "degC"},
    {"key": "payload.ipayload", "name": "Payload current (simulated)", "units": "A"},
    {"key": "payload.payload_state", "name": "Payload state (simulated)", "units": ""},
    {"key": "obc.tobc", "name": "OBC temperature (simulated)", "units": "degC"},
    {"key": "adcs.w_x", "name": "Angular velocity X (simulated)", "units": "rad/s"},
    {"key": "adcs.w_y", "name": "Angular velocity Y (simulated)", "units": "rad/s"},
    {"key": "adcs.w_z", "name": "Angular velocity Z (simulated)", "units": "rad/s"},
]


def telemetry_dictionary(extra_measurements=None):
    measurements = [
        {"key": "signal_power_dbfs", "name": "Signal power", "units": "dBFS"},
        {"key": "snr_db", "name": "Estimated SNR", "units": "dB"},
        {"key": "frequency_offset_hz", "name": "Frequency offset", "units": "Hz"},
        {"key": "frames_received", "name": "Frames received", "units": "count"},
        {"key": "frames_decoded", "name": "Frames decoded", "units": "count"},
        {"key": "frames_rejected", "name": "Frames rejected", "units": "count"},
    ] + SIMULATED_MEASUREMENTS
    known = {item["key"] for item in measurements}
    for item in extra_measurements or []:
        if item["key"] not in known:
            measurements.append(item)
            known.add(item["key"])
    return {
        "key": "ground-station",
        "name": "Modular Ground Station",
        "measurements": measurements,
    }
