from __future__ import annotations

import json
from pathlib import Path

from f1_engineer.config import DATA_DIR, Gender, PersonaId


class RapportStore:
    """Persistent 0–100 friendship score per persona+gender."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (DATA_DIR / "rapport.json")
        self._data: dict[str, float] = {}
        self._load()

    def _key(self, persona: PersonaId, gender: Gender) -> str:
        return f"{persona.value}:{gender.value}"

    def _load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, persona: PersonaId, gender: Gender) -> float:
        return float(self._data.get(self._key(persona, gender), 55.0))

    def adjust(self, persona: PersonaId, gender: Gender, delta: float) -> float:
        key = self._key(persona, gender)
        val = max(0.0, min(100.0, self.get(persona, gender) + delta))
        self._data[key] = val
        self.save()
        return val

    def describe(self, score: float) -> str:
        if score >= 80:
            return "close — warm banter OK"
        if score >= 60:
            return "good working relationship"
        if score >= 40:
            return "professional, a bit cool"
        if score >= 20:
            return "strained — keep it short and blunt"
        return "frosty — minimal banter, very curt"
