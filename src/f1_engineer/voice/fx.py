from __future__ import annotations

import numpy as np


def apply_radio_fx(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Light team-radio style bandpass + compression + noise floor."""
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)
    # normalize
    peak = np.max(np.abs(audio)) + 1e-8
    audio = audio / peak * 0.9

    # simple FFT bandpass ~300–3400 Hz
    n = len(audio)
    spec = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    mask = (freqs >= 300) & (freqs <= 3400)
    soft = np.zeros_like(spec)
    soft[mask] = spec[mask]
    # gentle roll-off outside
    audio = np.fft.irfft(soft, n=n).astype(np.float32)

    # soft compression
    abs_a = np.abs(audio)
    compressed = np.tanh(abs_a * 1.6) * np.sign(audio)
    # tiny noise floor
    noise = np.random.normal(0, 0.002, size=compressed.shape).astype(np.float32)
    out = compressed * 0.85 + noise
    peak = np.max(np.abs(out)) + 1e-8
    return (out / peak * 0.85).astype(np.float32)
