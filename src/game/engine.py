"""
src/game/engine.py — Game engine.

The central state machine that drives the game loop. It owns the run lifecycle
(IDLE -> COUNTDOWN -> PLAYING/DEMO -> FINISHED, with PAUSED off the play states),
exposes the current playback position ("scroll position") the renderer reads,
and orchestrates three injected collaborators: a timing clock, a scoring engine,
and (in demo mode) a demo input source.

The collaborators are injected through structural Protocols rather than
constructed here, so the engine can be built and unit-tested before the concrete
AudioPlayer (Phase 3.1), ScoringEngine (Phase 2.5), and DemoPlayer (Phase 2.6)
exist. See ai-working-log/specs/2026-06-02-game-engine-design.md.
"""
from __future__ import annotations

import math
from enum import Enum, auto
from typing import Protocol

from src.game.chart import Chart
from src.input.signal import InputSignal

COUNTDOWN_MS = 3000
END_PADDING_MS = 2000  # tail after the last note so it resolves and audio rings out


class GameState(Enum):
    IDLE = auto()
    COUNTDOWN = auto()
    PLAYING = auto()
    PAUSED = auto()
    DEMO = auto()
    FINISHED = auto()


class Clock(Protocol):
    """Timing authority. AudioPlayer (Phase 3.1) satisfies this structurally."""
    def play(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def stop(self) -> None: ...
    def current_ms(self) -> float: ...
    def is_playing(self) -> bool: ...


class Scoring(Protocol):
    """Scoring engine. ScoringEngine (Phase 2.5) satisfies this structurally."""
    def reset(self, chart: Chart) -> None: ...
    def register_hit(self, lane: int, time_ms: float) -> object: ...
    def tick(self, current_ms: float) -> None: ...


class DemoSource(Protocol):
    """Demo input generator. DemoPlayer (Phase 2.6) satisfies this structurally."""
    def tick(self, current_ms: float) -> list[InputSignal]: ...


class GameEngine:
    """State machine driving the game loop over injected collaborators."""

    def __init__(self, clock: Clock, scoring: Scoring, *,
                 countdown_ms: float = COUNTDOWN_MS,
                 end_padding_ms: float = END_PADDING_MS) -> None:
        self._clock = clock
        self._scoring = scoring
        self._countdown_ms = countdown_ms
        self._end_padding_ms = end_padding_ms

        self._chart: Chart | None = None
        self._demo_source: DemoSource | None = None
        self._state = GameState.IDLE
        self._countdown_elapsed = 0.0
        self._paused_from: GameState | None = None
        self._finished_ms = 0.0

    # --- Setup -------------------------------------------------------------

    def load(self, chart: Chart, demo_source: DemoSource | None = None) -> None:
        """Bind a chart (and optional demo source) and reset to a fresh run.

        Calls scoring.reset(chart) so a re-load clears prior score/combo state
        and binds scoring to the new chart's notes.
        """
        self._chart = chart
        self._demo_source = demo_source
        self._scoring.reset(chart)
        self._countdown_elapsed = 0.0
        self._paused_from = None
        self._finished_ms = 0.0
        self._state = GameState.IDLE

    # --- Lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Begin the 3-2-1 countdown. The clock starts only when play begins."""
        self._require_loaded()
        if self._state is not GameState.IDLE:
            raise RuntimeError(f"start() requires IDLE state, not {self._state.name}")
        self._countdown_elapsed = 0.0
        self._state = GameState.COUNTDOWN

    def update(self, dt_ms: float) -> None:
        """Advance one frame. dt_ms is the caller-supplied wall time elapsed."""
        self._require_loaded()

        if self._state is GameState.COUNTDOWN:
            self._countdown_elapsed += dt_ms
            if self._countdown_elapsed >= self._countdown_ms:
                self._clock.play()
                self._state = (GameState.DEMO if self._demo_source is not None
                               else GameState.PLAYING)
            return

        if self._state is GameState.PLAYING:
            now = self._clock.current_ms()
            self._scoring.tick(now)
            self._check_finish(now)
            return

        if self._state is GameState.DEMO:
            now = self._clock.current_ms()
            for sig in self._demo_source.tick(now):
                self._scoring.register_hit(sig.lane, sig.time_ms)
            self._scoring.tick(now)
            self._check_finish(now)
            return

        # IDLE, PAUSED, FINISHED: no-op.

    def handle_input(self, lane: int) -> None:
        """Register a real player hit. The engine stamps the time with the
        clock, so callers never supply heterogeneous device timestamps. Active
        only in PLAYING; a no-op everywhere else (notably DEMO)."""
        if self._state is GameState.PLAYING:
            self._scoring.register_hit(lane, self._clock.current_ms())

    def pause(self) -> None:
        """Pause from PLAYING/DEMO; no-op otherwise."""
        if self._state in (GameState.PLAYING, GameState.DEMO):
            self._paused_from = self._state
            self._state = GameState.PAUSED
            self._clock.pause()

    def resume(self) -> None:
        """Resume to the pre-pause play state; no-op unless PAUSED."""
        if self._state is GameState.PAUSED:
            self._state = self._paused_from or GameState.PLAYING
            self._paused_from = None
            self._clock.resume()

    # --- Queries -----------------------------------------------------------

    def current_ms(self) -> float:
        """The scroll-position authority the renderer reads.

        Negative pre-roll during IDLE/COUNTDOWN scrolls notes in during the
        3-2-1; FINISHED returns the time cached before clock.stop() so a
        position-resetting stop() cannot snap the scroll back to 0.
        """
        if self._state is GameState.IDLE:
            return -self._countdown_ms
        if self._state is GameState.COUNTDOWN:
            return self._countdown_elapsed - self._countdown_ms
        if self._state is GameState.FINISHED:
            return self._finished_ms
        return self._clock.current_ms()  # PLAYING, DEMO, PAUSED

    def countdown_value(self) -> int:
        """Whole seconds remaining in the countdown (3 -> 2 -> 1); 0 otherwise."""
        if self._state is not GameState.COUNTDOWN:
            return 0
        remaining = self._countdown_ms - self._countdown_elapsed
        ceiling = math.ceil(self._countdown_ms / 1000)
        return max(0, min(ceiling, math.ceil(remaining / 1000)))

    def is_demo(self) -> bool:
        """True when the active play state is demo, stable across a pause."""
        return (self._state is GameState.DEMO
                or (self._state is GameState.PAUSED
                    and self._paused_from is GameState.DEMO))

    def is_finished(self) -> bool:
        return self._state is GameState.FINISHED

    @property
    def state(self) -> GameState:
        return self._state

    # --- Internals ---------------------------------------------------------

    def _require_loaded(self) -> None:
        if self._chart is None:
            raise RuntimeError("no chart loaded; call load() first")

    def _check_finish(self, now: float) -> None:
        if now >= self._chart.total_duration_ms + self._end_padding_ms:
            self._finished_ms = now
            self._clock.stop()
            self._state = GameState.FINISHED
