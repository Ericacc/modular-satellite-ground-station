import numpy as np


def calculate_rf_metrics(iq_samples, sample_rate, center_frequency_hz=0):
    samples = np.asarray(iq_samples, dtype=np.complex128)
    if samples.ndim != 1 or samples.size < 16:
        raise ValueError("At least 16 one-dimensional IQ samples are required")
    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive")

    power = np.abs(samples) ** 2
    signal_power = float(np.mean(power))
    peak_power = float(np.max(power))

    window = np.hanning(samples.size)
    spectrum = np.abs(np.fft.fftshift(np.fft.fft(samples * window))) ** 2
    frequencies = np.fft.fftshift(np.fft.fftfreq(samples.size, 1 / sample_rate))
    peak_index = int(np.argmax(spectrum))

    guard = max(2, samples.size // 50)
    noise_bins = np.ones(samples.size, dtype=bool)
    noise_bins[max(0, peak_index - guard):min(samples.size, peak_index + guard + 1)] = False
    noise_power = float(np.median(spectrum[noise_bins]) / np.sum(window ** 2))
    noise_power = max(noise_power, np.finfo(float).tiny)
    signal_only = max(signal_power - noise_power, np.finfo(float).tiny)

    return {
        "signal_power_dbfs": float(10 * np.log10(max(signal_power, np.finfo(float).tiny))),
        "peak_power_dbfs": float(10 * np.log10(max(peak_power, np.finfo(float).tiny))),
        "noise_power_dbfs": float(10 * np.log10(noise_power)),
        "snr_db": float(10 * np.log10(signal_only / noise_power)),
        "frequency_peak_hz": float(center_frequency_hz + frequencies[peak_index]),
        "frequency_offset_hz": float(frequencies[peak_index]),
        "sample_count": int(samples.size),
    }

