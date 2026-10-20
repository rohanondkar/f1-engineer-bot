from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WeatherSnapshot:
    forecast_accuracy: int = 0
    track_temp: int = 0
    air_temp: int = 0
    rain_percentage: int = 0
    weather: int = 0  # 0 clear … 5 heavy rain


@dataclass
class CarSnapshot:
    position: int = 0
    current_lap: int = 0
    lap_distance: float = 0.0
    total_distance: float = 0.0
    last_lap_time_ms: int = 0
    current_lap_time_ms: int = 0
    sector1_ms: int = 0
    sector2_ms: int = 0
    sector: int = 0
    pit_status: int = 0
    num_pit_stops: int = 0
    penalties: int = 0
    warnings: int = 0
    driver_status: int = 0
    result_status: int = 0

    speed: int = 0
    throttle: float = 0.0
    brake: float = 0.0
    clutch: float = 0.0
    gear: int = 0
    eng_rpm: int = 0
    drs: int = 0
    tyres_surface_temp: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    tyres_inner_temp: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    tyres_pressure: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    engine_temp: int = 0

    fuel_mix: int = 0
    fuel_in_tank: float = 0.0
    fuel_remaining_laps: float = 0.0
    ers_store_energy: float = 0.0
    ers_deploy_mode: int = 0
    ers_harvested_this_lap_mguk: float = 0.0
    ers_harvested_this_lap_mguh: float = 0.0
    ers_deployed_this_lap: float = 0.0
    network_paused: int = 0
    vehicle_fia_flags: int = 0
    engine_power_ice: float = 0.0
    engine_power_mguk: float = 0.0

    tyres_wear: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    tyres_damage: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    brakes_damage: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    front_left_wing_damage: int = 0
    front_right_wing_damage: int = 0
    rear_wing_damage: int = 0
    floor_damage: int = 0
    diffuser_damage: int = 0
    sidepod_damage: int = 0
    drs_fault: int = 0
    engine_damage: int = 0
    gear_box_damage: int = 0
    tyre_blisters: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    actual_tyre_compound: int = 0
    visual_tyre_compound: int = 0
    tyres_age_laps: int = 0

    driver_name: str = ""
    team_id: int = 0
    race_number: int = 0


@dataclass
class SessionState:
    """Thread-safe live snapshot of the player's session."""

    connected: bool = False
    last_packet_at: float = 0.0
    packet_format: int = 0
    session_uid: int = 0
    session_time: float = 0.0
    frame_identifier: int = 0
    player_car_index: int = 0

    session_type: int = 0
    track_id: int = 0
    track_length: int = 0
    track_name: str = ""
    total_laps: int = 0
    session_time_left: int = 0
    session_duration: int = 0
    pit_speed_limit: int = 0
    game_paused: int = 0
    is_spectating: int = 0
    safety_car_status: int = 0  # 0 none, 1 full, 2 VSC, 3 formation
    network_game: int = 0
    forecast_accuracy: int = 0
    weather: WeatherSnapshot = field(default_factory=WeatherSnapshot)

    num_cars: int = 0
    player: CarSnapshot = field(default_factory=CarSnapshot)
    cars: list[CarSnapshot] = field(default_factory=list)

    gap_ahead_s: float | None = None
    gap_behind_s: float | None = None
    car_ahead_name: str = ""
    car_behind_name: str = ""

    last_event: str = ""
    last_event_at: float = 0.0

    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def touch(self) -> None:
        with self._lock:
            self.connected = True
            self.last_packet_at = time.time()

    def is_live(self, timeout: float = 3.0) -> bool:
        with self._lock:
            return self.connected and (time.time() - self.last_packet_at) < timeout

    def braking_hard(self, threshold: float = 0.55) -> bool:
        with self._lock:
            return self.player.brake >= threshold

    def mid_corner(self) -> bool:
        with self._lock:
            p = self.player
            return p.brake > 0.15 and p.throttle < 0.5 and p.speed > 40

    def snapshot_dict(self) -> dict[str, Any]:
        with self._lock:
            p = self.player
            return {
                "connected": self.is_live(),
                "track": self.track_name or str(self.track_id),
                "session_type": self.session_type,
                "laps_total": self.total_laps,
                "lap": p.current_lap,
                "position": p.position,
                "speed_kph": p.speed,
                "gear": p.gear,
                "throttle": round(p.throttle, 2),
                "brake": round(p.brake, 2),
                "fuel_laps": round(p.fuel_remaining_laps, 2),
                "fuel_kg": round(p.fuel_in_tank, 2),
                "ers_mode": p.ers_deploy_mode,
                "ers_pct": round((p.ers_store_energy / 4_000_000) * 100, 1)
                if p.ers_store_energy
                else 0.0,
                "tyre_compound": p.visual_tyre_compound,
                "tyre_age": p.tyres_age_laps,
                "tyre_wear": [round(w, 1) for w in p.tyres_wear],
                "tyre_temps_inner": list(p.tyres_inner_temp),
                "wing_damage_fl": p.front_left_wing_damage,
                "wing_damage_fr": p.front_right_wing_damage,
                "rear_wing_damage": p.rear_wing_damage,
                "engine_damage": p.engine_damage,
                "drs": p.drs,
                "safety_car": self.safety_car_status,
                "weather": self.weather.weather,
                "rain_pct": self.weather.rain_percentage,
                "track_temp": self.weather.track_temp,
                "gap_ahead_s": self.gap_ahead_s,
                "gap_behind_s": self.gap_behind_s,
                "car_ahead": self.car_ahead_name,
                "car_behind": self.car_behind_name,
                "last_lap_ms": p.last_lap_time_ms,
                "pit_status": p.pit_status,
                "penalties": p.penalties,
                "last_event": self.last_event,
            }

    def ensure_cars(self, n: int = 22) -> None:
        with self._lock:
            while len(self.cars) < n:
                self.cars.append(CarSnapshot())
            self.num_cars = n
