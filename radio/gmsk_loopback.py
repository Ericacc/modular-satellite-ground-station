#!/usr/bin/env python3
"""GNU Radio GMSK laboratory loopback using an AX.25/HDLC test frame."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aegissat.protocol.ax25 import build_ui_frame, parse_ui_frame
from aegissat.radio.config import load_gmsk_config, validate_gmsk_config
from aegissat.radio.hdlc import decode_hdlc_frames, encode_hdlc_frame


def run_loopback(ax25_frame):
    try:
        from gnuradio import blocks, digital, gr
    except ImportError as error:
        raise RuntimeError(
            "GNU Radio is required. Run this script in the GNU Radio environment."
        ) from error

    config = load_gmsk_config()
    validate_gmsk_config(config)
    transmitted_levels = encode_hdlc_frame(ax25_frame)

    graph = gr.top_block()
    source = blocks.vector_source_b(transmitted_levels, False)
    modulator = digital.gmsk_mod(
        samples_per_symbol=config.samples_per_symbol,
        bt=config.bt,
        verbose=False,
        log=False,
    )
    demodulator = digital.gmsk_demod(
        samples_per_symbol=config.samples_per_symbol,
        gain_mu=0.175,
        mu=0.5,
        omega_relative_limit=0.005,
        freq_error=0.0,
        verbose=False,
        log=False,
    )
    sink = blocks.vector_sink_b()
    graph.connect(source, modulator, demodulator, sink)
    graph.run()

    received = list(sink.data())
    candidates = decode_hdlc_frames(received)
    for candidate in candidates:
        try:
            parse_ui_frame(candidate, has_fcs=True)
            if candidate == ax25_frame:
                return config, candidate
        except ValueError:
            continue
    raise RuntimeError("The GMSK loopback did not recover the AX.25 frame")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--text", default="AegisSat GMSK laboratory validation"
    )
    args = parser.parse_args()
    frame = build_ui_frame("GROUND", "AEGIS", args.text.encode())
    config, recovered = run_loopback(frame)
    print("GMSK loopback passed")
    print(f"Profile: {config.profile}")
    print(f"Symbol rate: {config.symbol_rate:g} baud")
    print(f"Sample rate: {config.sample_rate:g} sample/s")
    print(f"BT: {config.bt:g}")
    print(f"Recovered AX.25 bytes: {len(recovered)}")


if __name__ == "__main__":
    main()
