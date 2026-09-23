import struct

COMMAND_PING = 1
COMMAND_REQUEST_TELEMETRY = 2
COMMAND_SET_MODE = 3


def encode_command(command_id, sequence, parameters=b""):
    if not isinstance(parameters, bytes):
        raise TypeError("Command parameters must be bytes")
    if len(parameters) > 255:
        raise ValueError("Command parameters cannot exceed 255 bytes")
    return struct.pack(">BBHB", 1, command_id, sequence, len(parameters)) + parameters


def decode_command(payload):
    if len(payload) < 5:
        raise ValueError("Satellite command is too short")
    version, command_id, sequence, length = struct.unpack(">BBHB", payload[:5])
    if version != 1 or len(payload) != 5 + length:
        raise ValueError("Invalid satellite command")
    return {
        "version": version,
        "command_id": command_id,
        "sequence": sequence,
        "parameters": payload[5:],
    }
