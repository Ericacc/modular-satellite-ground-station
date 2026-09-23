import struct

MAGIC = b"\xA5\x5A"
VERSION = 1
TYPE_TELEMETRY = 1
TYPE_COMMAND = 2
HEADER_FORMAT = ">2sBBIH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD_SIZE = 4096


def encode_message(message_type, sequence, payload):
    if not isinstance(payload, bytes):
        raise TypeError("IPC payload must be bytes")
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ValueError("IPC payload exceeds maximum size")
    header = struct.pack(
        HEADER_FORMAT, MAGIC, VERSION, message_type, sequence, len(payload)
    )
    return header + payload


def extract_messages(buffer):
    data = bytes(buffer)
    messages = []
    while True:
        magic_position = data.find(MAGIC)
        if magic_position < 0:
            return messages, data[-1:] if data.endswith(MAGIC[:1]) else b""
        data = data[magic_position:]
        if len(data) < HEADER_SIZE:
            return messages, data
        magic, version, message_type, sequence, length = struct.unpack(
            HEADER_FORMAT, data[:HEADER_SIZE]
        )
        if version != VERSION or length > MAX_PAYLOAD_SIZE:
            data = data[1:]
            continue
        total_size = HEADER_SIZE + length
        if len(data) < total_size:
            return messages, data
        messages.append({
            "type": message_type,
            "sequence": sequence,
            "payload": data[HEADER_SIZE:total_size],
        })
        data = data[total_size:]
