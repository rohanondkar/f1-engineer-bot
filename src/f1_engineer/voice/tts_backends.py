from __future__ import annotations

import asyncio
import io
import logging
import tempfile
from pathlib import Path

import numpy as np

from f1_engineer.voice.profiles import VoiceProfile

log = logging.getLogger(__name__)


async def synthesize_edge(text: str, profile: VoiceProfile) -> tuple[np.ndarray, int]:
    import edge_tts

    voice = profile.edge_voice or "en-US-AvaNeural"
    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    data = buf.getvalue()
    if not data:
        raise RuntimeError("edge-tts returned empty audio")
    return _decode_audio_bytes(data)


async def synthesize_elevenlabs(
    text: str,
    profile: VoiceProfile,
    api_key: str,
) -> tuple[np.ndarray, int]:
    import httpx

    voice_id = profile.elevenlabs_voice_id
    if not voice_id:
        # try to create IVC from reference if present
        voice_id = await ensure_elevenlabs_clone(profile, api_key)
        if not voice_id:
            raise RuntimeError("No ElevenLabs voice_id and no reference to clone")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.35, "similarity_boost": 0.85},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return _decode_audio_bytes(r.content)


async def ensure_elevenlabs_clone(profile: VoiceProfile, api_key: str) -> str | None:
    """Create Instant Voice Clone from reference.wav if needed; cache voice id."""
    ref = profile.reference_path()
    if not ref:
        return None
    cached = profile.dir / "elevenlabs_voice_id.txt"
    if cached.exists():
        vid = cached.read_text(encoding="utf-8").strip()
        if vid:
            profile.elevenlabs_voice_id = vid
            return vid

    import httpx

    url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {"xi-api-key": api_key}
    files = {"files": (ref.name, ref.read_bytes(), "audio/wav")}
    data = {
        "name": f"f1eng_{profile.id}",
        "description": f"F1 engineer clone {profile.display_name}",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, data=data, files=files)
        if r.status_code >= 400:
            log.warning("ElevenLabs IVC failed: %s %s", r.status_code, r.text[:200])
            return None
        body = r.json()
        vid = body.get("voice_id") or body.get("voiceId")
        if not vid:
            return None
        cached.write_text(vid, encoding="utf-8")
        profile.elevenlabs_voice_id = vid
        profile.save()
        return vid


def synthesize_local_clone_sync(text: str, profile: VoiceProfile) -> tuple[np.ndarray, int]:
    """Zero-shot local clone via Coqui XTTS if installed."""
    ref = profile.reference_path()
    if not ref:
        raise RuntimeError("Local clone needs reference.wav")

    try:
        from TTS.api import TTS
    except ImportError as e:
        raise RuntimeError("Install optional [xtts] extras for local cloning") from e

    # Lazy singleton
    global _XTTS
    if "_XTTS" not in globals() or _XTTS is None:
        _XTTS = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    tts = _XTTS

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.wav"
        tts.tts_to_file(
            text=text,
            file_path=str(out),
            speaker_wav=str(ref),
            language="en",
        )
        return _load_wav(out)


_XTTS = None


async def synthesize_local_clone(text: str, profile: VoiceProfile) -> tuple[np.ndarray, int]:
    return await asyncio.to_thread(synthesize_local_clone_sync, text, profile)


def _decode_audio_bytes(data: bytes) -> tuple[np.ndarray, int]:
    import soundfile as sf

    with io.BytesIO(data) as bio:
        try:
            audio, sr = sf.read(bio, dtype="float32")
            return np.asarray(audio, dtype=np.float32), int(sr)
        except Exception:
            pass

    # MP3 / other compressed (edge-tts, ElevenLabs)
    try:
        import miniaudio

        decoded = miniaudio.decode(data, nchannels=1, sample_rate=22050)
        samples = np.asarray(decoded.samples, dtype=np.float32)
        # miniaudio may give int16-scale floats depending on version
        peak = np.max(np.abs(samples)) + 1e-8
        if peak > 1.5:
            samples = samples / 32768.0
        return samples, int(decoded.sample_rate)
    except Exception:
        log.warning("miniaudio decode failed; trying temp wav path")

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(data)
        path = Path(f.name)
    try:
        return _load_wav(path)
    finally:
        path.unlink(missing_ok=True)


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf

    try:
        audio, sr = sf.read(str(path), dtype="float32")
        return np.asarray(audio, dtype=np.float32), int(sr)
    except Exception:
        # fallback: wave module for pcm wav only
        import wave

        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            frames = w.readframes(w.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            return audio, sr
