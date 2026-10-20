from __future__ import annotations

import asyncio
import logging
import tempfile
import threading
from pathlib import Path

import numpy as np

from f1_engineer.config import Settings, VoiceBackend
from f1_engineer.voice.fx import apply_radio_fx
from f1_engineer.voice.profiles import VoiceProfile, profile_for
from f1_engineer.voice import tts_backends

log = logging.getLogger(__name__)


class VoiceManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.degraded = False
        self.degraded_reason = ""
        self._speaking = False
        self._lock = threading.Lock()

    @property
    def speaking(self) -> bool:
        return self._speaking

    def resolve_profile(self, region=None, gender=None, profile_id: str = "") -> VoiceProfile:
        if profile_id:
            from f1_engineer.voice.profiles import get_profile

            p = get_profile(profile_id)
            if p:
                return p
        region = region or self.settings.engineer_region
        gender = gender or self.settings.engineer_gender
        return profile_for(region, gender)

    async def speak(self, text: str, profile: VoiceProfile | None = None) -> None:
        if self.settings.mute_audio or not text.strip():
            return
        profile = profile or self.resolve_profile()
        audio, sr = await self.synthesize(text, profile)
        if self.settings.radio_fx:
            audio = apply_radio_fx(audio, sr)
        await asyncio.to_thread(self._play, audio, sr)

    async def synthesize(self, text: str, profile: VoiceProfile) -> tuple[np.ndarray, int]:
        backend = self.settings.voice_backend
        order = self._backend_order(backend, profile)
        last_err: Exception | None = None
        for name in order:
            try:
                if name == "elevenlabs":
                    audio, sr = await tts_backends.synthesize_elevenlabs(
                        text, profile, self.settings.elevenlabs_api_key
                    )
                elif name == "local_clone":
                    audio, sr = await tts_backends.synthesize_local_clone(text, profile)
                else:
                    audio, sr = await tts_backends.synthesize_edge(text, profile)
                    if name == "edge" and len(order) > 1:
                        self.degraded = True
                        self.degraded_reason = "Using edge-tts fallback (add reference.wav or ElevenLabs key for natural clones)"
                self.degraded = name == "edge" and "elevenlabs" not in order and "local_clone" not in order
                return audio, sr
            except Exception as e:
                last_err = e
                log.warning("TTS backend %s failed: %s", name, e)
        # last resort edge
        try:
            self.degraded = True
            self.degraded_reason = f"Clone backends failed ({last_err}); edge-tts fallback"
            return await tts_backends.synthesize_edge(text, profile)
        except Exception as e:
            raise RuntimeError(f"All TTS backends failed: {e}") from e

    def _backend_order(self, backend: VoiceBackend, profile: VoiceProfile) -> list[str]:
        if backend == VoiceBackend.ELEVENLABS:
            return ["elevenlabs"]
        if backend == VoiceBackend.LOCAL_CLONE:
            return ["local_clone"]
        if backend == VoiceBackend.EDGE:
            return ["edge"]
        # auto
        order: list[str] = []
        if self.settings.elevenlabs_api_key and (profile.elevenlabs_voice_id or profile.reference_path()):
            order.append("elevenlabs")
        if profile.reference_path():
            order.append("local_clone")
        order.append("edge")
        return order

    def _play(self, audio: np.ndarray, sample_rate: int) -> None:
        with self._lock:
            self._speaking = True
        try:
            import sounddevice as sd

            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            sd.play(audio, sample_rate)
            sd.wait()
        except Exception:
            # mp3 path leftovers — write wav and try again
            try:
                import soundfile as sf

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    path = Path(f.name)
                sf.write(str(path), audio, sample_rate)
                self._play_file(path)
                path.unlink(missing_ok=True)
            except Exception:
                log.exception("Playback failed")
        finally:
            with self._lock:
                self._speaking = False

    def _play_file(self, path: Path) -> None:
        try:
            import sounddevice as sd
            import soundfile as sf

            data, sr = sf.read(str(path), dtype="float32")
            sd.play(data, sr)
            sd.wait()
        except Exception:
            try:
                from playsound import playsound  # type: ignore

                playsound(str(path))
            except Exception:
                log.exception("File playback failed")
