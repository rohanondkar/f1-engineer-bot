from __future__ import annotations

import asyncio
import logging
import math
import random
import time

from f1_engineer.state.session import CarSnapshot, SessionState, WeatherSnapshot

log = logging.getLogger(__name__)


class MockTelemetry:
    """Simulates a race so the engineer can be developed without F1 26 running."""

    def __init__(self, state: SessionState) -> None:
        self.state = state
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Mock telemetry started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        t0 = time.time()
        lap = 1
        wear = [8.0, 7.5, 9.0, 8.5]
        fuel = 45.0
        pos = 4
        while self._running:
            elapsed = time.time() - t0
            phase = (elapsed % 90) / 90.0
            speed = int(180 + 100 * math.sin(phase * math.pi * 2))
            brake = max(0.0, math.sin(phase * math.pi * 4)) if phase > 0.4 and phase < 0.55 else 0.0
            throttle = 0.2 if brake > 0.3 else 0.85

            if int(elapsed) % 95 == 0 and int(elapsed) > 0:
                lap += 1
                wear = [min(100.0, w + random.uniform(2.5, 4.5)) for w in wear]
                fuel = max(0.0, fuel - random.uniform(1.6, 2.2))

            sc = 1 if 200 < elapsed < 230 else 0
            event = ""
            if int(elapsed) == 201:
                event = "SCAR"
            elif int(elapsed) == 231:
                event = "SEND"

            gap_ahead = 1.1 + 0.4 * math.sin(elapsed / 11)
            gap_behind = 0.9 + 0.5 * math.cos(elapsed / 9)

            with self.state._lock:
                self.state.connected = True
                self.state.last_packet_at = time.time()
                self.state.packet_format = 2026
                self.state.session_time = elapsed
                self.state.track_id = 10
                self.state.track_name = "Spa"
                self.state.total_laps = 44
                self.state.session_type = 15
                self.state.safety_car_status = sc
                self.state.weather = WeatherSnapshot(
                    weather=1 if elapsed > 300 else 0,
                    track_temp=38,
                    air_temp=22,
                    rain_percentage=15 if elapsed > 300 else 0,
                )
                if event:
                    self.state.last_event = event
                    self.state.last_event_at = elapsed

                p = CarSnapshot(
                    position=pos,
                    current_lap=lap,
                    speed=speed,
                    throttle=throttle,
                    brake=brake,
                    gear=max(1, min(8, speed // 40)),
                    fuel_in_tank=fuel,
                    fuel_remaining_laps=fuel / 1.9,
                    ers_store_energy=2_500_000 + 500_000 * math.sin(elapsed / 7),
                    ers_deploy_mode=2,
                    visual_tyre_compound=16,
                    tyres_age_laps=lap - 1,
                    tyres_wear=list(wear),
                    tyres_inner_temp=[95, 93, 98, 96],
                    front_left_wing_damage=5 if elapsed > 400 else 0,
                    driver_name="Player",
                    last_lap_time_ms=108_500 + random.randint(-400, 400),
                )
                self.state.player = p
                self.state.ensure_cars(22)
                self.state.cars[0] = p
                self.state.gap_ahead_s = gap_ahead
                self.state.gap_behind_s = gap_behind
                self.state.car_ahead_name = "Verstappen"
                self.state.car_behind_name = "Norris"

            await asyncio.sleep(0.25)
