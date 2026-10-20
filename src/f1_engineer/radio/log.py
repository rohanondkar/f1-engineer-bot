from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class RadioMessage:
    speaker: str
    text: str
    kind: str = "call"  # call | reply | driver | system
    ts: float = field(default_factory=time.time)


class RadioLog:
    def __init__(self, maxlen: int = 200) -> None:
        self._messages: deque[RadioMessage] = deque(maxlen=maxlen)
        self._listeners: list[Callable[[RadioMessage], None]] = []

    def add(self, msg: RadioMessage) -> None:
        self._messages.append(msg)
        for cb in list(self._listeners):
            try:
                cb(msg)
            except Exception:
                pass

    def subscribe(self, cb: Callable[[RadioMessage], None]) -> None:
        self._listeners.append(cb)

    def recent(self, n: int = 50) -> list[RadioMessage]:
        return list(self._messages)[-n:]
