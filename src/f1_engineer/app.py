from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from f1_engineer.config import (
    Gender,
    PersonaId,
    Region,
    Settings,
    Talkativeness,
    get_settings,
)
from f1_engineer.insights.comms_gate import CommsGate
from f1_engineer.insights.engine import InsightEngine
from f1_engineer.mock.simulator import MockTelemetry
from f1_engineer.personas.catalog import EngineerPresentation, presentation_for
from f1_engineer.personas.rapport import RapportStore
from f1_engineer.radio.llm import RadioLLM
from f1_engineer.radio.log import RadioLog, RadioMessage
from f1_engineer.state.session import SessionState
from f1_engineer.telemetry.udp import TelemetryListener
from f1_engineer.voice.manager import VoiceManager
from f1_engineer.voice.profiles import VoiceProfile, ensure_default_profiles, import_voice, list_profiles

log = logging.getLogger(__name__)


@dataclass
class EngineerApp:
    settings: Settings = field(default_factory=get_settings)
    state: SessionState = field(default_factory=SessionState)
    radio_log: RadioLog = field(default_factory=RadioLog)
    rapport: RapportStore = field(default_factory=RapportStore)
    insights: InsightEngine = field(default_factory=InsightEngine)
    gate: CommsGate = field(init=False)
    llm: RadioLLM = field(init=False)
    voice: VoiceManager = field(init=False)
    presentation: EngineerPresentation = field(init=False)

    _listener: TelemetryListener | None = None
    _mock: MockTelemetry | None = None
    _tasks: list[asyncio.Task] = field(default_factory=list)
    _running: bool = False
    on_status: Callable[[str], None] | None = None

    def __post_init__(self) -> None:
        ensure_default_profiles()
        self.gate = CommsGate(talkativeness=self.settings.talkativeness)
        self.llm = RadioLLM(self.settings, self.rapport)
        self.voice = VoiceManager(self.settings)
        self.presentation = presentation_for(
            self.settings.engineer_persona,
            self.settings.engineer_gender,
            self.settings.engineer_region,
            voice_profile_id=self.settings.voice_profile_id,
        )

    def status(self, msg: str) -> None:
        log.info(msg)
        if self.on_status:
            self.on_status(msg)

    def set_persona(self, persona: PersonaId) -> None:
        self.settings.engineer_persona = persona
        self._refresh_presentation()

    def set_gender(self, gender: Gender) -> None:
        self.settings.engineer_gender = gender
        self._refresh_presentation()

    def set_region(self, region: Region) -> None:
        self.settings.engineer_region = region
        self._refresh_presentation()

    def set_voice_profile(self, profile_id: str) -> None:
        self.settings.voice_profile_id = profile_id
        self._refresh_presentation()

    def set_talkativeness(self, value: Talkativeness) -> None:
        self.settings.talkativeness = value
        self.gate.set_talkativeness(value)

    def set_mute(self, muted: bool) -> None:
        # Mute only silences TTS; transcript / proactive calls still flow
        self.settings.mute_audio = muted

    def set_radio_fx(self, enabled: bool) -> None:
        self.settings.radio_fx = enabled

    def _refresh_presentation(self) -> None:
        self.presentation = presentation_for(
            self.settings.engineer_persona,
            self.settings.engineer_gender,
            self.settings.engineer_region,
            voice_profile_id=self.settings.voice_profile_id,
        )
        self.radio_log.add(
            RadioMessage(
                speaker="System",
                text=f"Engineer: {self.presentation.display_name} ({self.presentation.persona.label})",
                kind="system",
            )
        )

    def rapport_score(self) -> float:
        return self.rapport.get(self.presentation.persona.id, self.presentation.gender)

    def profiles(self) -> list[VoiceProfile]:
        return list_profiles()

    def import_voice_file(self, path: str, display_name: str) -> VoiceProfile:
        from pathlib import Path

        profile = import_voice(
            Path(path),
            display_name=display_name or "Custom Engineer",
            gender=self.settings.engineer_gender,
            region=self.settings.engineer_region,
        )
        self.set_voice_profile(profile.id)
        return profile

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.radio_log.add(
            RadioMessage(
                speaker="System",
                text=f"Online - {self.presentation.display_name} ready. Waiting for F1 26 telemetry...",
                kind="system",
            )
        )
        if self.settings.mock_telemetry:
            self._mock = MockTelemetry(self.state)
            await self._mock.start()
            self.status("Mock telemetry running")
        else:
            self._listener = TelemetryListener(
                self.state,
                host=self.settings.udp_host,
                port=self.settings.udp_port,
                on_event=lambda code: None,
            )
            await self._listener.start()
            self.status(f"UDP listening on port {self.settings.udp_port}")

        self._tasks.append(asyncio.create_task(self._insight_loop()))
        self._tasks.append(asyncio.create_task(self._comms_loop()))

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        if self._listener:
            await self._listener.stop()
        if self._mock:
            await self._mock.stop()

    async def _insight_loop(self) -> None:
        while self._running:
            try:
                insights = self.insights.evaluate(self.state)
                self.gate.submit(insights, self.state)
            except Exception:
                log.exception("insight loop error")
            await asyncio.sleep(0.5)

    async def _comms_loop(self) -> None:
        while self._running:
            try:
                self.gate.speaking = self.voice.speaking
                insight = self.gate.pop_ready(self.state)
                if insight:
                    await self._deliver_insight(insight)
            except Exception:
                log.exception("comms loop error")
            await asyncio.sleep(0.2)

    async def _deliver_insight(self, insight) -> None:
        eng = self.presentation
        # specialty boost: prefer template for specialty kinds when offline
        text = self.llm.phrase_insight(insight, eng, self.state.snapshot_dict())
        self.radio_log.add(RadioMessage(speaker=eng.display_name, text=text, kind="call"))
        profile = self.voice.resolve_profile(
            eng.region, eng.gender, self.settings.voice_profile_id or eng.voice_profile_id
        )
        self.gate.speaking = True
        try:
            await self.voice.speak(text, profile)
        finally:
            self.gate.speaking = False

        # rapport nudges
        if insight.kind in ("tire_cliff", "fuel_low", "damage", "safety_car"):
            self.rapport.adjust(eng.persona.id, eng.gender, 0.5)

    async def handle_driver_text(self, text: str, *, from_voice: bool = False) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        eng = self.presentation
        self.radio_log.add(
            RadioMessage(speaker="You", text=text, kind="driver")
        )
        # simple rapport from tone
        low = text.lower()
        if any(w in low for w in ("shut up", "stupid", "useless", "quiet")):
            self.rapport.adjust(eng.persona.id, eng.gender, -4)
        elif any(w in low for w in ("thanks", "copy", "good call", "nice")):
            self.rapport.adjust(eng.persona.id, eng.gender, 2)

        self.gate.ptt_active = True
        try:
            reply = await asyncio.to_thread(
                self.llm.answer,
                text,
                eng,
                self.state.snapshot_dict(),
                from_voice=from_voice,
            )
        finally:
            self.gate.ptt_active = False

        self.radio_log.add(RadioMessage(speaker=eng.display_name, text=reply, kind="reply"))
        profile = self.voice.resolve_profile(
            eng.region, eng.gender, self.settings.voice_profile_id or eng.voice_profile_id
        )
        await self.voice.speak(reply, profile)
        return reply

    async def handle_ptt_audio(self, audio, sample_rate: int = 16000) -> str:
        from f1_engineer.voice.stt import transcribe_array

        self.gate.ptt_active = True
        try:
            text = await asyncio.to_thread(transcribe_array, audio, sample_rate)
        finally:
            self.gate.ptt_active = False
        if not text:
            return ""
        return await self.handle_driver_text(text, from_voice=True)

    def connection_label(self) -> str:
        if self.state.is_live():
            track = self.state.track_name or "session"
            return f"Live - {track} | P{self.state.player.position} | L{self.state.player.current_lap}"
        if self.settings.mock_telemetry:
            return "Mock telemetry"
        return "Listening for F1 26..."

    def snapshot(self) -> dict[str, Any]:
        return {
            "connection": self.connection_label(),
            "engineer": self.presentation.display_name,
            "persona": self.presentation.persona.label,
            "gender": self.presentation.gender.value,
            "region": self.presentation.region.value,
            "rapport": self.rapport_score(),
            "degraded_voice": self.voice.degraded,
            "degraded_reason": self.voice.degraded_reason,
            "llm": self.llm.available(),
            "mute": self.settings.mute_audio,
        }
