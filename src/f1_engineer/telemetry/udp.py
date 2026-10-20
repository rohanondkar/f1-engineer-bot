from __future__ import annotations

import asyncio
import logging
import struct
from typing import Callable

from f1_engineer.state.session import CarSnapshot, SessionState, WeatherSnapshot
from f1_engineer.telemetry.packets import (
    HEADER_SIZE,
    TRACK_NAMES,
    PacketId,
    event_code,
    parse_header,
)

log = logging.getLogger(__name__)

# Fallback entry sizes when packet length division is unavailable
LAP_DATA_SIZE = 57
CAR_TELEMETRY_SIZE = 60
CAR_STATUS_SIZE = 55
CAR_DAMAGE_SIZE = 42
PARTICIPANT_NAME_LEN = 32


class TelemetryListener:
    """Async UDP listener that updates SessionState."""

    def __init__(
        self,
        state: SessionState,
        host: str = "127.0.0.1",
        port: int = 20777,
        on_event: Callable[[str], None] | None = None,
    ) -> None:
        self.state = state
        self.host = host
        self.port = port
        self.on_event = on_event
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: asyncio.DatagramProtocol | None = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        class Proto(asyncio.DatagramProtocol):
            def __init__(self, outer: TelemetryListener) -> None:
                self.outer = outer

            def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001
                try:
                    self.outer._handle(data)
                except Exception:
                    log.exception("telemetry parse error")

        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: Proto(self),
            local_addr=(self.host if self.host != "127.0.0.1" else "0.0.0.0", self.port),
        )
        log.info("Listening for F1 UDP on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None

    def _handle(self, data: bytes) -> None:
        header = parse_header(data)
        if header is None:
            return
        s = self.state
        s.touch()
        with s._lock:
            s.packet_format = header.packet_format
            s.session_uid = header.session_uid
            s.session_time = header.session_time
            s.frame_identifier = header.frame_identifier
            s.player_car_index = header.player_car_index

        pid = header.packet_id
        if pid == PacketId.SESSION:
            self._parse_session(data, header.player_car_index)
        elif pid == PacketId.LAP_DATA:
            self._parse_lap(data, header.player_car_index)
        elif pid == PacketId.CAR_TELEMETRY:
            self._parse_car_telemetry(data, header.player_car_index)
        elif pid == PacketId.CAR_STATUS:
            self._parse_car_status(data, header.player_car_index)
        elif pid == PacketId.CAR_DAMAGE:
            self._parse_car_damage(data, header.player_car_index)
        elif pid == PacketId.PARTICIPANTS:
            self._parse_participants(data, header.player_car_index)
        elif pid == PacketId.EVENT:
            self._parse_event(data)

    def _parse_session(self, data: bytes, player_idx: int) -> None:
        # PacketSessionData after header — key fields at known offsets for F1 24+
        # weather(u8), trackTemp(i8), airTemp(i8), totalLaps(u8), trackLength(u16),
        # sessionType(u8), trackId(i8), formula(u8), sessionTimeLeft(u16), ...
        off = HEADER_SIZE
        if len(data) < off + 20:
            return
        weather, track_temp, air_temp, total_laps = struct.unpack_from("<BbbB", data, off)
        track_length = struct.unpack_from("<H", data, off + 4)[0]
        session_type, track_id = struct.unpack_from("<Bb", data, off + 6)
        session_time_left = struct.unpack_from("<H", data, off + 9)[0]
        # safetyCarStatus is later — scan common offset (~near end of early block)
        # F1 25: after pitSpeedLimit etc. Use a safer read if packet long enough.
        safety_car = 0
        if len(data) >= off + 30:
            # approximate: safetyCarStatus around offset 27 from header in recent formats
            safety_car = data[off + 27] if len(data) > off + 27 else 0

        with self.state._lock:
            self.state.weather = WeatherSnapshot(
                weather=weather,
                track_temp=track_temp,
                air_temp=air_temp,
            )
            self.state.total_laps = total_laps
            self.state.track_length = track_length
            self.state.session_type = session_type
            self.state.track_id = track_id
            self.state.track_name = TRACK_NAMES.get(track_id, f"Track {track_id}")
            self.state.session_time_left = session_time_left
            self.state.safety_car_status = safety_car

    def _parse_lap(self, data: bytes, player_idx: int) -> None:
        self.state.ensure_cars(22)
        off = HEADER_SIZE
        # Try structured unpack; if size mismatch, fall back to partial reads
        entry_size = LAP_DATA_SIZE
        # F1 25 LapData is larger — detect by remaining length
        remaining = len(data) - off
        if remaining >= 22 * 50:
            entry_size = remaining // 22

        for i in range(22):
            base = off + i * entry_size
            if base + 24 > len(data):
                break
            last_lap, current_lap, sector1, sector2 = struct.unpack_from("<IIII", data, base)
            # floats: lapDistance, totalDistance often follow
            lap_dist, total_dist = 0.0, 0.0
            if base + 24 <= len(data):
                try:
                    lap_dist, total_dist = struct.unpack_from("<ff", data, base + 16)
                except struct.error:
                    pass
            # position / currentLapNum near end of struct — use heuristic offsets
            car = self.state.cars[i]
            car.last_lap_time_ms = last_lap
            car.current_lap_time_ms = current_lap
            car.sector1_ms = sector1 & 0xFFFF
            car.sector2_ms = sector2 & 0xFFFF
            car.lap_distance = lap_dist
            car.total_distance = total_dist

            # In modern packets, carPosition is a uint8 near the middle/end
            # Scan a few candidate offsets relative to entry
            for cand in (31, 33, 35, 36, 39, 40):
                if base + cand < len(data):
                    pos = data[base + cand]
                    if 1 <= pos <= 22:
                        car.position = pos
                        break
            for cand in (32, 34, 37, 38, 41):
                if base + cand < len(data):
                    lapn = data[base + cand]
                    if 0 < lapn < 200:
                        car.current_lap = lapn
                        break

        self._update_player_from_cars(player_idx)
        self._update_gaps(player_idx)

    def _parse_car_telemetry(self, data: bytes, player_idx: int) -> None:
        self.state.ensure_cars(22)
        off = HEADER_SIZE
        remaining = len(data) - off
        # exclude trailing mfdPanelIndex etc (~3 bytes) — divide by 22
        entry_size = max(60, (remaining - 3) // 22) if remaining > 100 else CAR_TELEMETRY_SIZE

        for i in range(22):
            base = off + i * entry_size
            if base + 20 > len(data):
                break
            speed = struct.unpack_from("<H", data, base)[0]
            throttle, steer, brake = struct.unpack_from("<fff", data, base + 2)
            clutch = data[base + 14] if base + 15 <= len(data) else 0
            gear = struct.unpack_from("<b", data, base + 15)[0] if base + 16 <= len(data) else 0
            eng_rpm = struct.unpack_from("<H", data, base + 16)[0] if base + 18 <= len(data) else 0
            drs = data[base + 18] if base + 19 <= len(data) else 0

            car = self.state.cars[i]
            car.speed = speed
            car.throttle = throttle
            car.brake = brake
            car.clutch = clutch / 100.0 if clutch > 1 else float(clutch)
            car.gear = gear
            car.eng_rpm = eng_rpm
            car.drs = drs

            # tyre temps often after — try common layout
            # skip to surface temps if enough bytes
            if base + 45 <= len(data):
                try:
                    temps = struct.unpack_from("<4H", data, base + 24)
                    car.tyres_surface_temp = list(temps)
                except struct.error:
                    pass
            if base + 53 <= len(data):
                try:
                    inners = struct.unpack_from("<4H", data, base + 32)
                    car.tyres_inner_temp = list(inners)
                except struct.error:
                    pass

        self._update_player_from_cars(player_idx)

    def _parse_car_status(self, data: bytes, player_idx: int) -> None:
        self.state.ensure_cars(22)
        off = HEADER_SIZE
        remaining = len(data) - off
        entry_size = remaining // 22 if remaining >= 22 * 40 else CAR_STATUS_SIZE

        for i in range(22):
            base = off + i * entry_size
            if base + 30 > len(data):
                break
            car = self.state.cars[i]
            # tractionControl, antiLockBrakes, fuelMix, frontBrakeBias, fuelInTank...
            fuel_mix = data[base + 2] if base + 3 <= len(data) else 0
            fuel_in_tank = struct.unpack_from("<f", data, base + 4)[0] if base + 8 <= len(data) else 0.0
            # fuelRemainingLaps often at +12
            fuel_laps = struct.unpack_from("<f", data, base + 12)[0] if base + 16 <= len(data) else 0.0
            # visualTyreCompound / tyresAgeLaps / flags / ers — search floats for ERS store
            car.fuel_mix = fuel_mix
            car.fuel_in_tank = fuel_in_tank
            car.fuel_remaining_laps = fuel_laps

            # F1 25 CarStatus: actualTyreCompound, visualTyreCompound, tyresAgeLaps near mid
            for cand, attr, cast in (
                (24, "actual_tyre_compound", int),
                (25, "visual_tyre_compound", int),
                (26, "tyres_age_laps", int),
            ):
                if base + cand < len(data):
                    setattr(car, attr, cast(data[base + cand]))

            # ERS store energy is a float — try offsets
            for foff in (40, 44, 48, 36):
                if base + foff + 4 <= len(data):
                    val = struct.unpack_from("<f", data, base + foff)[0]
                    if 0 < val < 5_000_000:
                        car.ers_store_energy = val
                        break
            for cand in (45, 49, 53, 37):
                if base + cand < len(data) and data[base + cand] <= 5:
                    car.ers_deploy_mode = data[base + cand]
                    break

        self._update_player_from_cars(player_idx)

    def _parse_car_damage(self, data: bytes, player_idx: int) -> None:
        self.state.ensure_cars(22)
        off = HEADER_SIZE
        remaining = len(data) - off
        entry_size = remaining // 22 if remaining >= 22 * 40 else CAR_DAMAGE_SIZE

        for i in range(22):
            base = off + i * entry_size
            if base + 40 > len(data):
                break
            car = self.state.cars[i]
            try:
                wears = struct.unpack_from("<4f", data, base)
                car.tyres_wear = [float(w) for w in wears]
            except struct.error:
                continue
            # tyre damage 4B, brakes 4B then wings...
            b = base + 16
            if b + 20 <= len(data):
                car.tyres_damage = list(data[b : b + 4])
                car.brakes_damage = list(data[b + 4 : b + 8])
                car.front_left_wing_damage = data[b + 8]
                car.front_right_wing_damage = data[b + 9]
                car.rear_wing_damage = data[b + 10]
                car.floor_damage = data[b + 11]
                car.diffuser_damage = data[b + 12]
                car.sidepod_damage = data[b + 13]
                # engineDamage / gearBoxDamage further along
                if b + 20 < len(data):
                    car.engine_damage = data[b + 18] if b + 19 < len(data) else car.engine_damage
                    car.gear_box_damage = data[b + 19] if b + 20 < len(data) else car.gear_box_damage

        self._update_player_from_cars(player_idx)

    def _parse_participants(self, data: bytes, player_idx: int) -> None:
        self.state.ensure_cars(22)
        off = HEADER_SIZE
        if len(data) < off + 2:
            return
        num_active = data[off]
        # each participant: aiControlled(u8), driverId, networkId, teamId, myTeam, raceNumber, nationality, name[32|48], ...
        entry_size = (len(data) - off - 1) // 22 if len(data) > off + 1 else 56
        for i in range(min(22, num_active or 22)):
            base = off + 1 + i * entry_size
            if base + 40 > len(data):
                break
            team_id = data[base + 3]
            race_number = data[base + 5]
            name_off = base + 7
            raw = data[name_off : name_off + PARTICIPANT_NAME_LEN]
            name = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
            car = self.state.cars[i]
            car.team_id = team_id
            car.race_number = race_number
            if name:
                car.driver_name = name
        self._update_player_from_cars(player_idx)

    def _parse_event(self, data: bytes) -> None:
        code = event_code(data)
        if not code:
            return
        with self.state._lock:
            self.state.last_event = code
            self.state.last_event_at = self.state.session_time
        if self.on_event:
            self.on_event(code)

    def _update_player_from_cars(self, player_idx: int) -> None:
        with self.state._lock:
            if 0 <= player_idx < len(self.state.cars):
                # copy fields onto player snapshot
                src = self.state.cars[player_idx]
                self.state.player = src

    def _update_gaps(self, player_idx: int) -> None:
        with self.state._lock:
            if player_idx >= len(self.state.cars):
                return
            me = self.state.cars[player_idx]
            my_pos = me.position
            if my_pos <= 0:
                return
            ahead = behind = None
            for c in self.state.cars:
                if c.position == my_pos - 1 and my_pos > 1:
                    ahead = c
                if c.position == my_pos + 1:
                    behind = c

            def gap(a: CarSnapshot, b: CarSnapshot) -> float | None:
                # total_distance based estimate
                if a.total_distance and b.total_distance:
                    dist = abs(a.total_distance - b.total_distance)
                    # rough time from speed of trailing car
                    spd = max(b.speed, a.speed, 1)
                    return dist / (spd / 3.6) if spd > 30 else dist / 50.0
                return None

            if ahead:
                self.state.gap_ahead_s = gap(ahead, me)
                self.state.car_ahead_name = ahead.driver_name or f"P{ahead.position}"
            else:
                self.state.gap_ahead_s = None
                self.state.car_ahead_name = ""
            if behind:
                self.state.gap_behind_s = gap(me, behind)
                self.state.car_behind_name = behind.driver_name or f"P{behind.position}"
            else:
                self.state.gap_behind_s = None
                self.state.car_behind_name = ""
