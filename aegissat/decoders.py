"""Decoder registry for optional, satellite-specific telemetry adapters."""


class DecoderRegistry:
    def __init__(self):
        self._decoders = {}

    def register(self, name, decoder):
        self._decoders[name] = decoder

    def get(self, name):
        return self._decoders.get(name)

    def decode(self, name, frame):
        decoder = self.get(name)
        if decoder is None:
            return None
        return decoder(frame)

    def available(self):
        return sorted(self._decoders)


decoder_registry = DecoderRegistry()

