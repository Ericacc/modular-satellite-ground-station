#!/usr/bin/env python3
import argparse
import base64
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

from aegissat.doppler import calculate_doppler, create_doppler_tracker
from aegissat.radio.metrics import calculate_rf_metrics


running = True


def post_json(base_url, path, payload):
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return response.read()


def stop_handler(signum, frame):
    global running
    running = False


def forward_kiss(base_url, port, pass_id):
    while running:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=3) as client:
                client.settimeout(1)
                while running:
                    try:
                        chunk = client.recv(8192)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    post_json(base_url, "/ingest/external-kiss", {
                        "data_base64": base64.b64encode(chunk).decode("ascii"),
                        "pass_id": pass_id,
                    })
        except (OSError, TimeoutError):
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="RTL-SDR automatic receiver")
    parser.add_argument("--decoder", default="iq_recording")
    parser.add_argument("--satellite", required=True)
    parser.add_argument("--norad-id", type=int, default=0)
    parser.add_argument("--frequency", required=True, type=float)
    parser.add_argument("--sample-rate", type=float, default=48000)
    parser.add_argument("--rtl-sample-rate", type=float, default=240000)
    parser.add_argument("--pass-id", required=True)
    args = parser.parse_args()

    use_gr_satellites = args.decoder == "gr_satellites"
    if use_gr_satellites and shutil.which("gr_satellites") is None:
        raise SystemExit("gr_satellites is required by this local override")
    try:
        from rtlsdr import RtlSdr
    except Exception as error:
        raise SystemExit(f"pyrtlsdr/RTL-SDR could not be loaded: {error}") from error

    base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    udp_port = int(os.getenv("GR_SATELLITES_UDP_PORT", "7355"))
    kiss_port = int(os.getenv("GR_SATELLITES_KISS_PORT", "8100"))
    signal_offset_hz = float(os.getenv("SIGNAL_OFFSET_HZ", "12000"))
    fll_bw_hz = float(os.getenv("GR_SATELLITES_FLL_BW_HZ", "100"))
    decoder_offset_hz = float(
        os.getenv(
            "GR_SATELLITES_F_OFFSET_HZ",
            str(signal_offset_hz),
        )
    )

    doppler_enabled = (
        os.getenv("DOPPLER_ENABLED", "true").lower()
        in {"1", "true", "yes", "on"}
        and args.norad_id > 0
    )
    doppler_interval = float(
        os.getenv("DOPPLER_UPDATE_SECONDS", "1.0")
    )
    doppler_tracker = None

    if doppler_enabled:
        try:
            doppler_tracker = create_doppler_tracker(
                args.norad_id
            )
            print(
                f"Doppler correction enabled for NORAD "
                f"{args.norad_id}",
                flush=True,
            )
        except Exception as error:
            print(
                f"Doppler correction unavailable: {error}. "
                "Using nominal frequency.",
                file=sys.stderr,
                flush=True,
            )
    decoder = None
    kiss_thread = None
    if use_gr_satellites:
        command = [
            "gr_satellites", str(args.satellite), "--udp", "--udp_raw", "--udp_ipv4_only", "--iq",
            "--samp_rate", str(args.rtl_sample_rate), "--udp_port", str(udp_port),
            "--f_offset", str(decoder_offset_hz), "--fll_bw", str(fll_bw_hz),
            "--kiss_server", str(kiss_port), "--kiss_server_address", "127.0.0.1",
        ]
        decoder = subprocess.Popen(command)
        kiss_thread = threading.Thread(
            target=forward_kiss, args=(base_url, kiss_port, args.pass_id), daemon=True
        )
        kiss_thread.start()

    sdr = RtlSdr(device_index=int(os.getenv("RTL_DEVICE_INDEX", "0")))
    sdr.sample_rate = args.rtl_sample_rate
    signal_frequency = float(args.frequency)
    current_frequency = signal_frequency - signal_offset_hz
    sdr.center_freq = current_frequency
    gain = os.getenv("RTL_GAIN", "auto")
    sdr.gain = "auto" if gain.lower() == "auto" else float(gain)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    iq_dir = Path(os.getenv("IQ_RECORDING_DIR", "data/iq"))
    iq_dir.mkdir(parents=True, exist_ok=True)
    iq_file = open(iq_dir / f"{args.pass_id}.c64", "ab")
    last_metrics = 0.0
    last_doppler = 0.0
    decoder_doppler_hz = 0.0
    decoder_phase = 0.0

    try:
        while running and (decoder is None or decoder.poll() is None):

            now = time.monotonic()

            if (
                doppler_tracker is not None
                and now - last_doppler >= doppler_interval
            ):
                try:
                    doppler = calculate_doppler(
                        doppler_tracker,
                        args.frequency,
                    )
                    decoder_doppler_hz = float(
                        doppler["doppler_shift_hz"]
                    )

                    print("Doppler update:", flush=True)
                    print(
                        f"  shift: "
                        f"{doppler['doppler_shift_hz']:+.1f} Hz",
                        flush=True,
                    )
                    print(
                        f"  fixed SDR frequency: "
                        f"{current_frequency:.1f} Hz",
                        flush=True,
                    )
                    print(
                        f"  digital correction: "
                        f"{-decoder_doppler_hz:+.1f} Hz",
                        flush=True,
                    )
                    print(
                        f"  elevation: "
                        f"{doppler['elevation_deg']:.1f} deg",
                        flush=True,
                    )
                except Exception as error:
                    print(
                        f"Doppler update failed: {error}",
                        file=sys.stderr,
                        flush=True,
                    )

                last_doppler = now
            samples = np.asarray(sdr.read_samples(16384), dtype=np.complex64)
            raw = samples.astype("<c8", copy=False).tobytes()
            iq_file.write(raw)

            if decoder is not None:
                indices = np.arange(
                    len(samples),
                    dtype=np.float64,
                )
                angles = (
                    decoder_phase
                    + 2.0
                    * np.pi
                    * decoder_doppler_hz
                    * indices
                    / args.rtl_sample_rate
                )
                decoder_samples = (
                    samples * np.exp(-1j * angles)
                ).astype("<c8")

                decoder_phase = float(
                    (
                        decoder_phase
                        + 2.0
                        * np.pi
                        * decoder_doppler_hz
                        * len(samples)
                        / args.rtl_sample_rate
                    )
                    % (2.0 * np.pi)
                )

                decoder_raw = decoder_samples.tobytes()
                for offset in range(0, len(decoder_raw), 1472):
                    udp.sendto(
                        decoder_raw[offset:offset + 1472],
                        ("127.0.0.1", udp_port),
                    )
            if time.monotonic() - last_metrics >= 2:
                metrics = calculate_rf_metrics(
                    samples,
                    args.rtl_sample_rate,
                    current_frequency,
                )
                metrics["pass_id"] = args.pass_id
                post_json(base_url, "/ingest/rf-metrics", metrics)
                last_metrics = time.monotonic()
    finally:
        sdr.close()
        iq_file.close()
        udp.close()
        if decoder is not None and decoder.poll() is None:
            decoder.terminate()
            try:
                decoder.wait(timeout=5)
            except subprocess.TimeoutExpired:
                decoder.kill()
        if kiss_thread is not None:
            kiss_thread.join(timeout=2)
    return 0 if decoder is None else decoder.returncode or 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    sys.exit(main())
