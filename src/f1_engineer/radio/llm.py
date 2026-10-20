from __future__ import annotations

import logging
from typing import Any

from f1_engineer.config import Settings
from f1_engineer.insights.engine import Insight
from f1_engineer.personas.catalog import EngineerPresentation
from f1_engineer.personas.rapport import RapportStore

log = logging.getLogger(__name__)


SYSTEM_BASE = """You are an F1 race engineer on the team radio to your driver.
Rules:
- Speak English only. Short team-radio style: 1–2 sentences max.
- No chatbot fluff, no markdown, no lists.
- Use real session data you are given — never invent fake telemetry numbers.
- Sound natural and human (light "uh—" / "checking…" only on non-urgent Q&A, never on safety).
- Match your persona, gender presentation, and rapport tone.
- Accent is handled by TTS; do not write phonetic accent spellings.
"""


class RadioLLM:
    def __init__(self, settings: Settings, rapport: RapportStore) -> None:
        self.settings = settings
        self.rapport = rapport
        self._client = None
        if settings.openai_api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=settings.openai_api_key)
            except Exception:
                log.exception("Failed to init OpenAI client")

    def available(self) -> bool:
        return self._client is not None

    def _persona_block(self, eng: EngineerPresentation) -> str:
        score = self.rapport.get(eng.persona.id, eng.gender)
        tone = self.rapport.describe(score)
        she_he, her_him, hers_his = eng.pronouns
        return (
            f"Your name is {eng.display_name}. You are a {eng.gender.value} engineer "
            f"from {eng.region.value.upper()} (English with that regional accent in voice). "
            f"Persona: {eng.persona.label}. {eng.persona.system_flavor} "
            f"Rapport with driver: {score:.0f}/100 — {tone}. "
            f"Pronouns: {she_he}/{her_him}/{hers_his}. "
            f"Catchphrase bank (use sparingly): {', '.join(eng.persona.catchphrases[:3])}."
        )

    def phrase_insight(self, insight: Insight, eng: EngineerPresentation, state: dict[str, Any]) -> str:
        # Fast path without LLM
        if not self._client:
            return insight.template_hint or "Copy."

        user = (
            f"Proactive radio call.\n"
            f"Insight kind: {insight.kind} (priority {insight.priority.name}).\n"
            f"Hint: {insight.template_hint}\n"
            f"Session data: {state}\n"
            f"Rewrite as a natural radio call. Keep numbers accurate."
        )
        return self._complete(eng, user, fallback=insight.template_hint or "Copy.")

    def answer(
        self,
        question: str,
        eng: EngineerPresentation,
        state: dict[str, Any],
        *,
        from_voice: bool = False,
    ) -> str:
        if not self._client:
            return self._offline_answer(question, state)

        style = "Driver spoke on radio." if from_voice else "Driver typed on radio chat."
        user = (
            f"{style}\n"
            f"Driver: {question}\n"
            f"Session data: {state}\n"
            f"Answer as their race engineer. Short. Use data when relevant."
        )
        return self._complete(eng, user, fallback="Copy. We're checking.")

    def _complete(self, eng: EngineerPresentation, user: str, fallback: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0.55,
                max_tokens=120,
                messages=[
                    {"role": "system", "content": SYSTEM_BASE + "\n" + self._persona_block(eng)},
                    {"role": "user", "content": user},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            # strip quotes if model wraps
            if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
                text = text[1:-1].strip()
            return text or fallback
        except Exception:
            log.exception("LLM call failed")
            return fallback

    def _offline_answer(self, question: str, state: dict[str, Any]) -> str:
        q = question.lower()
        if "gap" in q and "behind" in q:
            g = state.get("gap_behind_s")
            return f"Gap behind {g:.1f}." if g is not None else "No one immediately behind."
        if "gap" in q or "ahead" in q:
            g = state.get("gap_ahead_s")
            return f"Gap ahead {g:.1f}." if g is not None else "You're leading or gap unknown."
        if "tyre" in q or "tire" in q:
            w = state.get("tyre_wear") or []
            return f"Tyre wear {', '.join(f'{x:.0f}%' for x in w)}. Age {state.get('tyre_age')} laps."
        if "fuel" in q:
            return f"Fuel for about {state.get('fuel_laps', 0):.1f} laps."
        if "position" in q or "where am i" in q:
            return f"P{state.get('position')}, lap {state.get('lap')}."
        if "temp" in q:
            return f"Inner tyre temps {state.get('tyre_temps_inner')}."
        return "Copy. We're checking — set OPENAI_API_KEY for full radio."
