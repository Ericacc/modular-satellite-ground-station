AX25_CONTROL_UI = 0x03
AX25_PID_NO_LAYER_3 = 0xF0


def encode_address(callsign, ssid=0, last=False):
    callsign = callsign.upper().strip()
    if not callsign or len(callsign) > 6:
        raise ValueError("AX.25 callsign must contain 1 to 6 characters")
    if not 0 <= ssid <= 15:
        raise ValueError("AX.25 SSID must be between 0 and 15")
    encoded = bytes(ord(char) << 1 for char in callsign.ljust(6))
    final_byte = 0x60 | (ssid << 1) | int(last)
    return encoded + bytes([final_byte])


def decode_address(data):
    if len(data) != 7:
        raise ValueError("AX.25 address must contain 7 bytes")
    callsign = "".join(chr(byte >> 1) for byte in data[:6]).strip()
    return callsign, (data[6] >> 1) & 0x0F


def calculate_fcs(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF


def build_ui_frame(destination, source, information,
                   destination_ssid=0, source_ssid=0, include_fcs=True):
    if not isinstance(information, bytes):
        raise TypeError("AX.25 information must be bytes")
    frame = (
        encode_address(destination, destination_ssid, False)
        + encode_address(source, source_ssid, True)
        + bytes([AX25_CONTROL_UI, AX25_PID_NO_LAYER_3])
        + information
    )
    if include_fcs:
        frame += calculate_fcs(frame).to_bytes(2, "little")
    return frame


def parse_ui_frame(frame, has_fcs=True):
    if len(frame) < 18 if has_fcs else len(frame) < 16:
        raise ValueError("AX.25 frame is too short")
    body = frame
    fcs_valid = None
    if has_fcs:
        body = frame[:-2]
        received_fcs = int.from_bytes(frame[-2:], "little")
        fcs_valid = received_fcs == calculate_fcs(body)
        if not fcs_valid:
            raise ValueError("Invalid AX.25 FCS")
    if body[14] != AX25_CONTROL_UI or body[15] != AX25_PID_NO_LAYER_3:
        raise ValueError("Only AX.25 UI frames with PID 0xF0 are supported")
    destination, destination_ssid = decode_address(body[:7])
    source, source_ssid = decode_address(body[7:14])
    return {
        "destination": destination,
        "destination_ssid": destination_ssid,
        "source": source,
        "source_ssid": source_ssid,
        "information": body[16:],
        "fcs_valid": fcs_valid,
    }
