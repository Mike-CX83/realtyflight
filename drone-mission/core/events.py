"""Append-only mission event log — the immutable audit trail (doc 08 §8).

One SQLite table, insert-only. No UPDATE, no DELETE — corrections are new
events. Rebuilding a mission's story = reading its events in seq order; the
UI timeline, the replay view, and the capstone report all fold this table.

Clock discipline: the log never reads the wall clock; the owner injects a
`clock` callable (the executor's clock), so tests are fully deterministic.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mission_id: str
    seq: int
    ts: float
    type: str            # e.g. "step.dispatched", "fault.raised", "state.transition"
    payload: dict[str, Any]


class EventLog:
    """SQLite-backed append-only log. Use path=':memory:' in tests."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mission_events (
                mission_id TEXT NOT NULL,
                seq        INTEGER NOT NULL,
                ts         REAL NOT NULL,
                type       TEXT NOT NULL,
                payload    TEXT NOT NULL,
                PRIMARY KEY (mission_id, seq)
            )
            """
        )
        self._conn.commit()

    def append(self, mission_id: str, ts: float, type_: str, payload: dict[str, Any]) -> Event:
        cur = self._conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM mission_events WHERE mission_id = ?",
            (mission_id,),
        )
        seq = int(cur.fetchone()[0])
        self._conn.execute(
            "INSERT INTO mission_events (mission_id, seq, ts, type, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (mission_id, seq, ts, type_, json.dumps(payload, sort_keys=True)),
        )
        self._conn.commit()
        return Event(mission_id=mission_id, seq=seq, ts=ts, type=type_, payload=payload)

    def replay(self, mission_id: str) -> list[Event]:
        cur = self._conn.execute(
            "SELECT mission_id, seq, ts, type, payload FROM mission_events "
            "WHERE mission_id = ? ORDER BY seq",
            (mission_id,),
        )
        return [
            Event(mission_id=m, seq=s, ts=t, type=ty, payload=json.loads(p))
            for (m, s, t, ty, p) in cur.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()


class MissionRecorder:
    """Convenience wrapper binding one mission + one clock to the log."""

    def __init__(self, log: EventLog, mission_id: str, clock: Callable[[], float]) -> None:
        self._log = log
        self._mission_id = mission_id
        self._clock = clock

    def record(self, type_: str, **payload: Any) -> Event:
        return self._log.append(self._mission_id, self._clock(), type_, payload)
