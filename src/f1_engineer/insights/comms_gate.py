from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from f1_engineer.config import Talkativeness
from f1_engineer.insights.engine import Insight, InsightPriority
from f1_engineer.state.session import SessionState


@dataclass
class CommsGate:
    """Rate-limit, prioritize, and brake-aware mute for radio calls."""

    talkativeness: Talkativeness = Talkativeness.NORMAL
    speaking: bool = False
    ptt_active: bool = False

    _last_kind: dict[str, float] = field(default_factory=dict)
    _queue: deque[Insight] = field(default_factory=deque)
    _last_emit: float = 0.0

    def set_talkativeness(self, value: Talkativeness) -> None:
        self.talkativeness = value

    def _cooldowns(self) -> dict[str, float]:
        # base seconds between same kind
        scale = {
            Talkativeness.QUIET: 1.8,
            Talkativeness.NORMAL: 1.0,
            Talkativeness.CHATTY: 0.55,
        }[self.talkativeness]
        base = {
            "session_start": 9999,
            "session_end": 9999,
            "safety_car": 8,
            "safety_car_end": 8,
            "tire_cliff": 90,
            "fuel_low": 90,
            "damage": 25,
            "gap_ahead_close": 18,
            "gap_behind_threat": 18,
            "weather_rain": 120,
            "lap_complete": 25 if self.talkativeness != Talkativeness.CHATTY else 12,
            "drs_enabled": 40,
            "drs_disabled": 40,
            "banter": 60,
        }
        return {k: v * scale for k, v in base.items()}

    def _min_gap(self) -> float:
        return {
            Talkativeness.QUIET: 12.0,
            Talkativeness.NORMAL: 6.0,
            Talkativeness.CHATTY: 3.0,
        }[self.talkativeness]

    def _allows_priority_while_braking(self, p: InsightPriority) -> bool:
        # Only safety cuts through heavy braking / mid-corner
        return p >= InsightPriority.SAFETY

    def submit(self, insights: list[Insight], state: SessionState) -> None:
        now = time.time()
        cds = self._cooldowns()
        for insight in sorted(insights, key=lambda i: i.priority, reverse=True):
            if self.talkativeness == Talkativeness.QUIET and insight.priority <= InsightPriority.INFO:
                if insight.kind not in ("session_start", "session_end", "chequered", "race_winner"):
                    continue
            last = self._last_kind.get(insight.kind, 0.0)
            cd = cds.get(insight.kind, 20.0)
            if now - last < cd:
                continue
            # brake awareness
            if state.braking_hard() or state.mid_corner():
                if not self._allows_priority_while_braking(insight.priority):
                    continue
            self._queue.append(insight)

    def pop_ready(self, state: SessionState) -> Insight | None:
        if self.speaking or self.ptt_active:
            return None
        now = time.time()
        if now - self._last_emit < self._min_gap():
            # still allow SAFETY to jump if queued
            safety = next((i for i in self._queue if i.priority >= InsightPriority.SAFETY), None)
            if not safety or now - self._last_emit < 1.5:
                return None

        if not self._queue:
            return None

        # Prefer highest priority
        best_idx = max(range(len(self._queue)), key=lambda i: self._queue[i].priority)
        insight = self._queue[best_idx]
        del self._queue[best_idx]

        if (state.braking_hard() or state.mid_corner()) and not self._allows_priority_while_braking(
            insight.priority
        ):
            # re-queue
            self._queue.appendleft(insight)
            return None

        self._last_kind[insight.kind] = now
        self._last_emit = now
        return insight

    def clear(self) -> None:
        self._queue.clear()
