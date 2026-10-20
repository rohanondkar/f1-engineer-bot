from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        # small/base is fine for radio commands; CPU int8 for broad compatibility
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


def transcribe_array(audio: np.ndarray, sample_rate: int = 16000) -> str:
    if audio.size == 0:
        return ""
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    # resample rough if needed
    if sample_rate != 16000:
        import scipy.signal

        audio = scipy.signal.resample(audio, int(len(audio) * 16000 / sample_rate))
        sample_rate = 16000
    audio = audio.astype(np.float32)
    model = _get_model()
    segments, _info = model.transcribe(audio, language="en", vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    return text


def record_seconds(seconds: float = 4.0, sample_rate: int = 16000) -> np.ndarray:
    import sounddevice as sd

    frames = int(seconds * sample_rate)
    audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()
    return audio.reshape(-1)
