#!/usr/bin/env python3

import argparse
import time
import wave

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def calculate_spectrum(samples, fft_size):
    if len(samples) < fft_size:
        padded = np.zeros(
            fft_size,
            dtype=np.complex64
        )

        padded[:len(samples)] = samples
        samples = padded

    window = np.hanning(fft_size)

    spectrum = np.fft.fftshift(
        np.fft.fft(
            samples[:fft_size] * window
        )
    )

    power = 20 * np.log10(
        np.abs(spectrum) + 1e-12
    )

    return power


def open_window(sample_rate, fft_size, title):
    rows = 250

    waterfall = np.full(
        (rows, fft_size),
        -100.0
    )

    plt.ion()

    fig, ax = plt.subplots(
        figsize=(11, 6)
    )

    image = ax.imshow(
        waterfall,
        aspect="auto",
        origin="upper",
        extent=[
            -sample_rate / 2000,
            sample_rate / 2000,
            rows,
            0
        ],
        vmin=-100,
        vmax=0
    )

    ax.set_title(title)

    ax.set_xlabel(
        "Frequency offset (kHz)"
    )

    ax.set_ylabel(
        "Time"
    )

    fig.colorbar(
        image,
        ax=ax,
        label="Relative power (dB)"
    )

    fig.tight_layout()

    return fig, image, waterfall


def read_wav(path):
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        width = wav.getsampwidth()

        frames = wav.readframes(
            wav.getnframes()
        )

    if width == 1:

        samples = np.frombuffer(
            frames,
            dtype=np.uint8
        ).astype(np.float32)

        samples = (
            samples - 128
        ) / 128.0

    elif width == 2:

        samples = np.frombuffer(
            frames,
            dtype="<i2"
        ).astype(np.float32)

        samples /= 32768.0

    elif width == 4:

        samples = np.frombuffer(
            frames,
            dtype="<i4"
        ).astype(np.float32)

        samples /= 2147483648.0

    else:

        raise RuntimeError(
            "Unsupported WAV format"
        )

    if channels > 1:

        samples = samples.reshape(
            -1,
            channels
        )

        samples = samples[:, 0]

    return (
        samples.astype(np.complex64),
        sample_rate
    )


def show_recording(
    path,
    fft_size,
    loop=False,
    speed=1.0
):
    print(
        f"Opening recording: {path}"
    )

    samples, sample_rate = read_wav(
        path
    )

    fig, image, waterfall = open_window(
        sample_rate,
        fft_size,
        f"AO-73 recording waterfall - {path.name}"
    )

    block_time = fft_size / sample_rate

    delay = block_time / speed

    position = 0

    while plt.fignum_exists(
        fig.number
    ):

        end = position + fft_size

        if end > len(samples):

            if loop:
                position = 0
                continue

            break

        block = samples[
            position:end
        ]

        spectrum = calculate_spectrum(
            block,
            fft_size
        )

        waterfall[:-1] = waterfall[1:]
        waterfall[-1] = spectrum

        image.set_data(
            waterfall
        )

        fig.canvas.draw_idle()

        plt.pause(
            max(delay, 0.001)
        )

        position += fft_size

    plt.ioff()

    if plt.fignum_exists(
        fig.number
    ):
        plt.show()


def show_live(
    iq_dir,
    sample_rate,
    fft_size
):
    started_at = time.time()

    print(
        "Waiting for reception IQ file..."
    )

    iq_file = None

    while iq_file is None:

        files = sorted(
            Path(iq_dir).glob("*.c64"),
            key=lambda path:
                path.stat().st_mtime,
            reverse=True
        )

        if files:

            newest = files[0]

            if (
                newest.stat().st_mtime
                >= started_at - 2
            ):
                iq_file = newest
                break

        time.sleep(0.5)


    print(
        f"Using {iq_file}"
    )


    fig, image, waterfall = open_window(
        sample_rate,
        fft_size,
        f"Live waterfall - {iq_file.stem}"
    )


    offset = 0


    while plt.fignum_exists(
        fig.number
    ):

        with iq_file.open("rb") as file:

            file.seek(offset)

            raw = file.read(
                fft_size * 8
            )

            if len(raw) == fft_size * 8:
                offset = file.tell()


        if len(raw) < fft_size * 8:

            time.sleep(0.1)
            plt.pause(0.01)

            continue


        samples = np.frombuffer(
            raw,
            dtype=np.complex64
        )


        spectrum = calculate_spectrum(
            samples,
            fft_size
        )


        waterfall[:-1] = waterfall[1:]
        waterfall[-1] = spectrum


        image.set_data(
            waterfall
        )


        fig.canvas.draw_idle()

        plt.pause(0.01)


def main():
    parser = argparse.ArgumentParser()


    parser.add_argument(
        "--recording"
    )


    parser.add_argument(
        "--iq-dir"
    )


    parser.add_argument(
        "--sample-rate",
        type=float,
        default=240000
    )


    parser.add_argument(
        "--fft-size",
        type=int,
        default=2048
    )


    parser.add_argument(
        "--loop",
        action="store_true"
    )


    parser.add_argument(
        "--speed",
        type=float,
        default=1.0
    )


    args = parser.parse_args()


    if args.recording:

        show_recording(
            Path(args.recording),
            args.fft_size,
            loop=args.loop,
            speed=args.speed
        )

        return


    if args.iq_dir:

        show_live(
            args.iq_dir,
            args.sample_rate,
            args.fft_size
        )

        return


    parser.error(
        "Use --recording or --iq-dir"
    )


if __name__ == "__main__":
    main()
