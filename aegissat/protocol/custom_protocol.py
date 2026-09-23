import struct

# ==========================================================
# TELEMETRY FORMAT 
# ==========================================================

TELEMETRY_FORMAT = (
    ">IQII"   # HEADER
    "8f"      # EPS
    "10f"     # ADCS
    "fBII"    # OBC
    "5f"      # COMMS
    "2fB"     # PAYLOAD
    "2f"      # WEATHER
    "B3f"     # ORBIT
    "3I"      # FLAGS
)

TELEMETRY_SIZE = struct.calcsize(TELEMETRY_FORMAT)

def encode_telemetry(data: dict) -> bytes:
    return struct.pack(
        TELEMETRY_FORMAT,

        # HEADER
        data["header"]["id_sat"],
        data["header"]["timestamp_ms"],
        data["header"]["time_alive"],
        data["header"]["counter_packs"],

        # EPS
        data["eps"]["vbat"],
        data["eps"]["ibat"],
        data["eps"]["tbat"],
        data["eps"]["vsolar1"],
        data["eps"]["isolar1"],
        data["eps"]["vsolar2"],
        data["eps"]["isolar2"],
        data["eps"]["teps"],

        # ADCS
        data["adcs"]["tadcs"],
        data["adcs"]["w_x"],
        data["adcs"]["w_y"],
        data["adcs"]["w_z"],
        data["adcs"]["mag_x"],
        data["adcs"]["mag_y"],
        data["adcs"]["mag_z"],
        data["adcs"]["sun_x"],
        data["adcs"]["sun_y"],
        data["adcs"]["sun_z"],

        # OBC
        data["obc"]["tobc"],
        data["obc"]["cpu_ocuppation"],
        data["obc"]["ram_free"],
        data["obc"]["flash_memory_ocuppation"],

        # COMMS
        data["comms"]["tx_power"],
        data["comms"]["rx_RSSI"],
        data["comms"]["rx_snr"],
        data["comms"]["message_error_rate"],
        data["comms"]["ber"],

        # PAYLOAD
        data["payload"]["tpayload"],
        data["payload"]["ipayload"],
        data["payload"]["payload_state"],

        # WEATHER
        data["weather"]["external_temp"],
        data["weather"]["solar_reception"],

        # ORBIT
        data["orbit"]["orbit_ID"],
        data["orbit"]["orbit_height"],
        data["orbit"]["orbit_latitude"],
        data["orbit"]["orbit_longitude"],

        # FLAGS
        data["flags"]["error_flag"],
        data["flags"]["start_flag"],
        data["flags"]["end_flag"],
    )



def decode_telemetry(packet: bytes) -> dict:

    if len(packet) != TELEMETRY_SIZE:
        raise ValueError(f"Invalid packet size: {len(packet)} != {TELEMETRY_SIZE}")

    values = struct.unpack(TELEMETRY_FORMAT, packet)

    i = 0

    # =========================
    # HEADER
    # =========================
    id_sat = values[i]; i += 1
    timestamp = values[i]; i += 1
    time_alive = values[i]; i += 1
    counter = values[i]; i += 1

    header = {
        "id_sat": id_sat,
        "timestamp_ms": timestamp,
        "time_alive": time_alive,
        "counter_packs": counter,
    }

    # =========================
    # EPS
    # =========================
    vbat = values[i]; i += 1
    ibat = values[i]; i += 1
    tbat = values[i]; i += 1
    vsolar1 = values[i]; i += 1
    isolar1 = values[i]; i += 1
    vsolar2 = values[i]; i += 1
    isolar2 = values[i]; i += 1
    teps = values[i]; i += 1

    eps = {
        "vbat": vbat,
        "ibat": ibat,
        "tbat": tbat,
        "vsolar1": vsolar1,
        "isolar1": isolar1,
        "vsolar2": vsolar2,
        "isolar2": isolar2,
        "teps": teps,
    }

    # =========================
    # ADCS
    # =========================
    tadcs = values[i]; i += 1
    w_x = values[i]; i += 1
    w_y = values[i]; i += 1
    w_z = values[i]; i += 1
    mag_x = values[i]; i += 1
    mag_y = values[i]; i += 1
    mag_z = values[i]; i += 1
    sun_x = values[i]; i += 1
    sun_y = values[i]; i += 1
    sun_z = values[i]; i += 1

    adcs = {
        "tadcs": tadcs,
        "w_x": w_x,
        "w_y": w_y,
        "w_z": w_z,
        "mag_x": mag_x,
        "mag_y": mag_y,
        "mag_z": mag_z,
        "sun_x": sun_x,
        "sun_y": sun_y,
        "sun_z": sun_z,
    }

    # =========================
    # OBC
    # =========================
    tobc = values[i]; i += 1
    cpu = values[i]; i += 1
    ram = values[i]; i += 1
    flash = values[i]; i += 1

    obc = {
        "tobc": tobc,
        "cpu_ocuppation": cpu,
        "ram_free": ram,
        "flash_memory_ocuppation": flash,
    }

    # =========================
    # COMMS
    # =========================
    tx_power = values[i]; i += 1
    rssi = values[i]; i += 1
    snr = values[i]; i += 1
    mer = values[i]; i += 1
    ber = values[i]; i += 1

    comms = {
        "tx_power": tx_power,
        "rx_RSSI": rssi,
        "rx_snr": snr,
        "message_error_rate": mer,
        "ber": ber,
    }

    # =========================
    # PAYLOAD
    # =========================
    tpayload = values[i]; i += 1
    ipayload = values[i]; i += 1
    state = values[i]; i += 1

    payload = {
        "tpayload": tpayload,
        "ipayload": ipayload,
        "payload_state": state,
    }

    # =========================
    # WEATHER
    # =========================
    ext_temp = values[i]; i += 1
    solar = values[i]; i += 1

    weather = {
        "external_temp": ext_temp,
        "solar_reception": solar,
    }

    # =========================
    # ORBIT
    # =========================
    orbit_id = values[i]; i += 1
    height = values[i]; i += 1
    lat = values[i]; i += 1
    lon = values[i]; i += 1

    orbit = {
        "orbit_ID": orbit_id,
        "orbit_height": height,
        "orbit_latitude": lat,
        "orbit_longitude": lon,
    }

    # =========================
    # FLAGS
    # =========================
    error = values[i]; i += 1
    start = values[i]; i += 1
    end = values[i]; i += 1

    flags = {
        "error_flag": error,
        "start_flag": start,
        "end_flag": end,
    }

    # =========================
    # FINAL STRUCT
    # =========================
    return {
        "header": header,
        "eps": eps,
        "adcs": adcs,
        "obc": obc,
        "comms": comms,
        "payload": payload,
        "weather": weather,
        "orbit": orbit,
        "flags": flags,
    }