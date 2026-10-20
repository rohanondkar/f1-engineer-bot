from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from f1_engineer.state.session import SessionState


class InsightPriority(IntEnum):
    BANTER = 0
    INFO = 1
    STRATEGY = 2
    SAFETY = 3


@dataclass
class Insight:
    kind: str
    priority: InsightPriority
    payload: dict[str, Any] = field(default_factory=dict)
    template_hint: str = ""
    created_at: float = field(default_factory=time.time)


class InsightEngine:
    """Threshold / event rules that emit Insight objects from SessionState."""

    def __init__(self) -> None:
        self._prev_sc = 0
        self._prev_event = ""
        self._prev_lap = 0
        self._prev_wing = (0, 0, 0)
        self._last_gap_ahead: float | None = None
        self._last_gap_behind: float | None = None
        self._announced_tire_cliff = False
        self._announced_fuel_low = False
        self._session_started = False

    def evaluate(self, state: SessionState) -> list[Insight]:
        out: list[Insight] = []
        snap = state.snapshot_dict()
        if not snap.get("connected"):
            return out

        if not self._session_started:
            self._session_started = True
            out.append(
                Insight(
                    kind="session_start",
                    priority=InsightPriority.INFO,
                    payload=snap,
                    template_hint=(
                        f"Radio check. We're live. Track {snap.get('track')}, "
                        f"P{snap.get('position')}."
                    ),
                )
            )

        # Safety car
        sc = snap.get("safety_car") or 0
        if sc and sc != self._prev_sc:
            label = {1: "Safety car", 2: "VSC", 3: "Formation lap"}.get(sc, "Safety car")
            out.append(
                Insight(
                    kind="safety_car",
                    priority=InsightPriority.SAFETY,
                    payload={"status": sc, "label": label, **snap},
                    template_hint=f"{label}. Box opposite if we need to. Stay sharp.",
                )
            )
        elif self._prev_sc and not sc:
            out.append(
                Insight(
                    kind="safety_car_end",
                    priority=InsightPriority.SAFETY,
                    payload=snap,
                    template_hint="Safety car in. Modes ready. Go racing.",
                )
            )
        self._prev_sc = sc

        # Events
        ev = snap.get("last_event") or ""
        if ev and ev != self._prev_event:
            self._prev_event = ev
            mapped = _event_insight(ev, snap)
            if mapped:
                out.append(mapped)

        # Tire wear cliff
        wears = snap.get("tyre_wear") or [0, 0, 0, 0]
        max_wear = max(wears) if wears else 0
        fl, fr, rl, rr = (wears + [0, 0, 0, 0])[:4]
        if max_wear >= 55 and not self._announced_tire_cliff:
            self._announced_tire_cliff = True
            worst = ["FL", "FR", "RL", "RR"][wears.index(max_wear)]
            out.append(
                Insight(
                    kind="tire_cliff",
                    priority=InsightPriority.STRATEGY,
                    payload={"worst": worst, "wear": wears, **snap},
                    template_hint=f"{worst} going hard — wear around {max_wear:.0f}%. Box this lap if we can.",
                )
            )
        elif max_wear < 40:
            self._announced_tire_cliff = False

        # Fuel
        fuel_laps = snap.get("fuel_laps") or 0
        if 0 < fuel_laps < 3.5 and not self._announced_fuel_low:
            self._announced_fuel_low = True
            out.append(
                Insight(
                    kind="fuel_low",
                    priority=InsightPriority.STRATEGY,
                    payload=snap,
                    template_hint=f"Fuel critical — about {fuel_laps:.1f} laps. Lift and coast, save mode.",
                )
            )
        elif fuel_laps >= 5:
            self._announced_fuel_low = False

        # Damage
        flw = snap.get("wing_damage_fl") or 0
        frw = snap.get("wing_damage_fr") or 0
        rw = snap.get("rear_wing_damage") or 0
        wing = (flw, frw, rw)
        if wing != self._prev_wing and max(wing) >= 20:
            parts = []
            if flw >= 20:
                parts.append("front-left wing")
            if frw >= 20:
                parts.append("front-right wing")
            if rw >= 20:
                parts.append("rear wing")
            out.append(
                Insight(
                    kind="damage",
                    priority=InsightPriority.SAFETY,
                    payload={"parts": parts, **snap},
                    template_hint=f"{', '.join(parts)} damaged. Keep it on track. We'll check.",
                )
            )
        self._prev_wing = wing

        # Gaps — undercut / attack windows
        ga = snap.get("gap_ahead_s")
        gb = snap.get("gap_behind_s")
        if ga is not None and self._last_gap_ahead is not None:
            if ga < 1.0 and (self._last_gap_ahead - ga) > 0.25:
                out.append(
                    Insight(
                        kind="gap_ahead_close",
                        priority=InsightPriority.STRATEGY,
                        payload=snap,
                        template_hint=f"Gap ahead {ga:.1f}. DRS window — attack now.",
                    )
                )
        if gb is not None and self._last_gap_behind is not None:
            if gb < 1.2 and gb < self._last_gap_behind - 0.2:
                out.append(
                    Insight(
                        kind="gap_behind_threat",
                        priority=InsightPriority.STRATEGY,
                        payload=snap,
                        template_hint=f"Gap behind {gb:.1f}. Defend — no mistakes.",
                    )
                )
        self._last_gap_ahead = ga
        self._last_gap_behind = gb

        # Weather rain spike
        rain = snap.get("rain_pct") or 0
        if rain >= 40 and snap.get("weather", 0) >= 2:
            out.append(
                Insight(
                    kind="weather_rain",
                    priority=InsightPriority.STRATEGY,
                    payload=snap,
                    template_hint=f"Rain building — {rain}% chance. Interested in intermediates if it sticks.",
                )
            )

        # New lap info
        lap = snap.get("lap") or 0
        if lap and lap != self._prev_lap and lap > 1:
            last = snap.get("last_lap_ms") or 0
            if last > 0:
                out.append(
                    Insight(
                        kind="lap_complete",
                        priority=InsightPriority.INFO,
                        payload=snap,
                        template_hint=f"Lap {lap - 1} done. Last lap {_fmt_lap(last)}. P{snap.get('position')}.",
                    )
                )
        self._prev_lap = lap

        return out


def _fmt_lap(ms: int) -> str:
    s = ms / 1000.0
    m = int(s // 60)
    rem = s - m * 60
    return f"{m}:{rem:06.3f}"


def _event_insight(code: str, snap: dict) -> Insight | None:
    mapping = {
        "SSTA": ("session_start", InsightPriority.INFO, "Green lights. Eyes forward."),
        "SEND": ("session_end", InsightPriority.INFO, "Chequered. Bring it home."),
        "DRSE": ("drs_enabled", InsightPriority.INFO, "DRS enabled."),
        "DRSD": ("drs_disabled", InsightPriority.INFO, "DRS disabled."),
        "CHQF": ("chequered", InsightPriority.INFO, "Chequered flag. Nice work."),
        "RCWN": ("race_winner", InsightPriority.INFO, "That's P1. Absolute masterclass."),
        "RTMT": ("retirement", InsightPriority.SAFETY, "Someone's out. Stay focused."),
        "FTLP": ("fastest_lap", InsightPriority.INFO, "Purple lap. Keep that pace."),
        "SPTP": ("speed_trap", InsightPriority.BANTER, "Good trap speed."),
        "PENA": ("penalty", InsightPriority.SAFETY, "Penalty. We'll manage it."),
        "SCAR": ("safety_car", InsightPriority.SAFETY, "Safety car deployed."),
        "VSCS": ("vsc", InsightPriority.SAFETY, "Virtual safety car."),
        "VSCE": ("vsc_end", InsightPriority.SAFETY, "VSC ending. Get ready."),
        "LIGHTS": ("lights", InsightPriority.INFO, "Lights out shortly."),
    }
    # Event codes are 4 chars; some may vary
    key = code[:4]
    if key not in mapping:
        return None
    kind, prio, hint = mapping[key]
    return Insight(kind=kind, priority=prio, payload=snap, template_hint=hint)
