"""
src/game/scoring.py — Hit detection and scoring.

Evaluates player input timing against expected note times and tracks score,
combo, accuracy, and rank. Satisfies the engine's `Scoring` Protocol
(reset/register_hit/tick). See DESIGN.md §6.

Hit windows (|press - note.time_ms|):
  PERFECT  ≤ 35 ms
  GREAT    ≤ 75 ms
  GOOD     ≤ 120 ms
  (outside any window: no note consumed)

Per-note score: base = 1_000_000 / total_notes; PERFECT ×1.0, GREAT ×0.7,
GOOD ×0.4. Accuracy = (PERFECT + GREAT) / total_notes.

Two kinds of MISS:
  - tick() timeout: a note whose GOOD window has fully passed without a hit is
    marked missed and resets the combo. This is the authoritative miss.
  - stray register_hit(): a press with no unresolved note in range returns
    Judgment.MISS but consumes no note and does not touch the combo — a phantom
    tap is free, so demo mode (which only presses at exact note times) stays
    perfect.
"""
from __future__ import annotations

from enum import Enum, auto

from src.game.chart import Chart, Note

PERFECT_MS = 35.0
GREAT_MS = 75.0
GOOD_MS = 120.0

# How long a successful hit lingers as a renderer spark (ms).
HIT_FX_WINDOW_MS = 180.0

_MULTIPLIER = {
    'PERFECT': 1.0,
    'GREAT': 0.7,
    'GOOD': 0.4,
}


class Judgment(Enum):
    PERFECT = auto()
    GREAT = auto()
    GOOD = auto()
    MISS = auto()


class ScoringEngine:
    """Stateful hit/score tracker for a single chart run."""

    def __init__(self) -> None:
        self._notes: list[Note] = []
        self._by_lane: dict[int, list[Note]] = {}
        self._total = 0
        self._base = 0.0
        self._score = 0.0
        self._combo = 0
        self._max_combo = 0
        self._perfect = 0
        self._great = 0
        self._good = 0
        self._miss = 0
        self._hit_events: list[tuple[float, int]] = []  # (time_ms, lane)

    def reset(self, chart: Chart) -> None:
        """Bind to a chart's notes and clear all run state.

        Clears each note's hit/missed flags so a re-run starts fresh; the
        renderer reads those flags, so scoring owns them during a run.
        """
        self._notes = list(chart.notes)
        self._by_lane = {}
        for n in self._notes:
            n.hit = False
            n.missed = False
            self._by_lane.setdefault(n.lane, []).append(n)
        self._total = len(self._notes)
        self._base = 1_000_000 / self._total if self._total else 0.0
        self._score = 0.0
        self._combo = 0
        self._max_combo = 0
        self._perfect = self._great = self._good = self._miss = 0
        self._hit_events = []

    def register_hit(self, lane: int, time_ms: float) -> Judgment:
        """Resolve the nearest unresolved note in *lane* within the GOOD window.

        Returns the grade; a press with no note in range returns MISS without
        consuming a note or resetting the combo.
        """
        best: Note | None = None
        best_dt = GOOD_MS
        for n in self._by_lane.get(lane, []):
            if n.hit or n.missed:
                continue
            dt = abs(n.time_ms - time_ms)
            if dt <= best_dt:
                best, best_dt = n, dt

        if best is None:
            return Judgment.MISS

        best.hit = True
        if best_dt <= PERFECT_MS:
            judgment, key, self._perfect = Judgment.PERFECT, 'PERFECT', self._perfect + 1
        elif best_dt <= GREAT_MS:
            judgment, key, self._great = Judgment.GREAT, 'GREAT', self._great + 1
        else:
            judgment, key, self._good = Judgment.GOOD, 'GOOD', self._good + 1

        self._score += self._base * _MULTIPLIER[key]
        self._combo += 1
        self._max_combo = max(self._max_combo, self._combo)
        self._hit_events.append((time_ms, lane))
        return judgment

    def tick(self, current_ms: float) -> None:
        """Mark notes whose GOOD window has fully passed as missed (combo reset)."""
        for n in self._notes:
            if not n.hit and not n.missed and current_ms > n.time_ms + GOOD_MS:
                n.missed = True
                self._miss += 1
                self._combo = 0

    def recent_hits(self, current_ms: float,
                    window_ms: float = HIT_FX_WINDOW_MS) -> list[tuple[int, float]]:
        """Active hit sparks as (lane, intensity) for *current_ms*.

        Intensity fades from 1.0 at the moment of the hit to 0.0 at *window_ms*
        later. Expired events are swept out as a side effect, so this is meant to
        be called once per frame by the renderer; events newer than *current_ms*
        (clock jitter) are retained but not emitted yet."""
        live: list[tuple[float, int]] = []
        sparks: list[tuple[int, float]] = []
        for time_ms, lane in self._hit_events:
            age = current_ms - time_ms
            if age > window_ms:
                continue  # faded out
            live.append((time_ms, lane))
            if age >= 0:
                sparks.append((lane, 1.0 - age / window_ms))
        self._hit_events = live
        return sparks

    @property
    def score(self) -> int:
        return int(round(self._score))

    @property
    def combo(self) -> int:
        return self._combo

    @property
    def max_combo(self) -> int:
        return self._max_combo

    @property
    def perfect(self) -> int:
        return self._perfect

    @property
    def great(self) -> int:
        return self._great

    @property
    def good(self) -> int:
        return self._good

    @property
    def miss(self) -> int:
        return self._miss

    @property
    def accuracy(self) -> float:
        if self._total == 0:
            return 1.0
        return (self._perfect + self._great) / self._total

    def rank(self) -> str:
        return self.rank_for(self.accuracy)

    @staticmethod
    def rank_for(accuracy: float) -> str:
        if accuracy >= 0.98:
            return 'S'
        if accuracy >= 0.90:
            return 'A'
        if accuracy >= 0.75:
            return 'B'
        if accuracy >= 0.60:
            return 'C'
        return 'D'
