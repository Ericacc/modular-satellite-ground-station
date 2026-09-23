# GMSK radio layer

This directory contains the GNU Radio validation entry point:

```bash
python radio/gmsk_loopback.py
```

It executes this laboratory chain:

`AX.25 + FCS -> HDLC stuffing/flags -> NRZI -> GNU Radio GMSK modulator
-> GNU Radio GMSK demodulator -> HDLC -> AX.25/FCS validation`

The default profile is deliberately named `laboratory_default`. Its values are
not claimed to be the final AegisSat-01 link parameters. Set them in `.env` or
the shell when the satellite specification is available:

```text
AEGIS_GMSK_PROFILE=aegissat_final
AEGIS_GMSK_CENTER_FREQUENCY_HZ=...
AEGIS_GMSK_SYMBOL_RATE=...
AEGIS_GMSK_SAMPLES_PER_SYMBOL=...
AEGIS_GMSK_BT=...
AEGIS_GMSK_FREQUENCY_DEVIATION_HZ=...
AEGIS_RTL_GAIN_DB=...
```

The loopback proves the software GMSK/AX.25 path without RF hardware. Live
reception additionally needs an RTL-SDR source, frequency translation/filtering,
carrier and timing recovery, and connection of the recovered HDLC frame stream
to the backend KISS input. Those values cannot be finalized safely before the
AegisSat-01 RF specification is defined.
