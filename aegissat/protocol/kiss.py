FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD


def encode_kiss_frame(ax25_frame):
    escaped = ax25_frame.replace(bytes([FESC]), bytes([FESC, TFESC]))
    escaped = escaped.replace(bytes([FEND]), bytes([FESC, TFEND]))
    return bytes([FEND, 0x00]) + escaped + bytes([FEND])


def decode_kiss_stream(data):
    frames = []
    for raw in data.split(bytes([FEND])):
        if not raw:
            continue
        if raw[0] & 0x0F:
            continue
        payload = raw[1:]
        payload = payload.replace(bytes([FESC, TFEND]), bytes([FEND]))
        payload = payload.replace(bytes([FESC, TFESC]), bytes([FESC]))
        if payload:
            frames.append(payload)
    return frames


class KISSStreamDecoder:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        if not isinstance(data, bytes):
            raise TypeError("KISS stream data must be bytes")
        self.buffer.extend(data)
        frames = []
        while FEND in self.buffer:
            first = self.buffer.find(FEND)
            if first:
                del self.buffer[:first]
            if len(self.buffer) < 2:
                break
            second = self.buffer.find(FEND, 1)
            if second < 0:
                break
            raw = bytes(self.buffer[:second + 1])
            del self.buffer[:second + 1]
            frames.extend(decode_kiss_stream(raw))
        return frames

    def finish(self):
        incomplete = bool(self.buffer.strip(bytes([FEND])))
        self.buffer.clear()
        return incomplete
