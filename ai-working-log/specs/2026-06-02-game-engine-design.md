# Game Engine — Design Spec

**DESIGN.md reference:** §9 (Game Engine)
**TRACKING.md reference:** Phase 2.4
**Date:** 2026-06-02

## Goal

Build `src/game/engine.py`: the central state machine that drives the game
loop. It owns the run lifecycle (countdown → play → finish), exposes the current
playback position ("scroll position") that the renderer reads, and orchestrates
its collaborators — the timing clock, the scoring engine, and (in demo mode) the
demo input source.

This is the first orchestration layer over the MIDI ingestion pipeline
(`MidiParser` → `classify` → `ChartBuilder`). It is built before its concrete
collaborators (`ScoringEngine` 2.5, `DemoPlayer` 2.6, `AudioPlayer` 3.1), so it
depends on them through injected interfaces rather than constructing them.

## Scope

In scope:
- `src/game/engine.py` — `GameState` enum, `Clock`/`Scoring`/`DemoSource`
  Protocols, and the `GameEngine` class.
- `src/input/` package (new) with `src/input/signal.py` — the `InputSignal`
  dataclass, the shared currency between input/demo producers and the engine.
- Full state machine: `IDLE → COUNTDOWN → PLAYING → PAUSED → FINISHED`, with the
  `DEMO` branch parallel to `PLAYING`.
- Countdown timing, finish detection, pause/resume, input routing, and the
  `current_ms()` scroll-position authority.

Out of scope:
- Concrete `ScoringEngine` (Phase 2.5), `DemoPlayer` (Phase 2.6), `AudioPlayer`
  (Phase 3.1). The engine is tested against fakes.
- Active-note culling / visibility windowing. The renderer derives each note's
  world Z from `current_ms()`; the engine does not maintain a visible-note list.
- Hold-note release signaling. `InputSignal` carries `lane` + `time_ms` only; the
  `release` type (DESIGN.md deferred issue §6) is a later concern.
- The setup/factory that wires real collaborators into a `GameEngine`. That lands
  with the phases that introduce those collaborators.

## Deviation from DESIGN.md §9 (intentional)

DESIGN.md §9 specifies `load(chart, audio_path, demo=False)` with the engine
internally constructing an `AudioPlayer` and a `DemoPlayer`. This spec inverts
that: **the engine receives its collaborators injected** and never constructs
them. Rationale:

- The collaborators do not exist yet; injection lets Phase 2.4 be built and
  fully unit-tested now against fakes, with zero rework when the real classes
  arrive (structural `Protocol` typing means they need no base class or import).
- It keeps the engine's single responsibility — driving state — uncoupled from
  audio decoding, scoring math, and demo generation.

A later setup/factory (introduced alongside Phase 3.1) constructs `AudioPlayer`,
`ScoringEngine`, and (optionally) `DemoPlayer`, then hands them to `GameEngine`.
DESIGN.md §9 is updated to describe the injected form.

## Data structures

### `src/input/signal.py`

```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class InputSignal:
    """A single player (or demo) input: hit lane L at time T (chart clock ms)."""
    lane: int
    time_ms: float
```

`src/input/__init__.py` is new and empty (package marker).

### `src/game/engine.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

from src.game.chart import Chart
from src.input.signal import InputSignal


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
```

`Scoring.register_hit` returns the scoring engine's `Judgment`; the engine
discards the return value (hit effects are a renderer concern, wired later), so
its annotation here is `object`.

`Scoring.reset(chart)` binds the scoring engine to the chart's notes and clears
score/combo/hit state. The engine is constructed with a persistent `scoring`
collaborator (it accumulates results the results screen queries after the run),
so `scoring` itself is not re-injected per run — instead `load()` calls
`scoring.reset(chart)` to (re)bind it. This is what makes the "`load` may be
called again to reset" promise enforceable. (`DemoSource`, by contrast, is a
per-`load` argument already bound to its chart at construction, so it needs no
reset hook.)

## `GameEngine`

```python
COUNTDOWN_MS = 3000
END_PADDING_MS = 2000  # tail after the last note so it resolves and audio rings out


class GameEngine:
    def __init__(self, clock: Clock, scoring: Scoring, *,
                 countdown_ms: float = COUNTDOWN_MS,
                 end_padding_ms: float = END_PADDING_MS) -> None: ...

    def load(self, chart: Chart, demo_source: DemoSource | None = None) -> None: ...

    def start(self) -> None: ...
    def update(self, dt_ms: float) -> None: ...
    def handle_input(self, lane: int) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...

    def current_ms(self) -> float: ...
    def countdown_value(self) -> int: ...
    def is_demo(self) -> bool: ...
    def is_finished(self) -> bool: ...

    @property
    def state(self) -> GameState: ...
```

### Construction & load

- `__init__` stores `clock`, `scoring`, `countdown_ms`, `end_padding_ms`. State is
  `IDLE`; no chart yet.
- `load(chart, demo_source=None)` stores the chart and optional demo source,
  calls `scoring.reset(chart)` to (re)bind scoring to this chart and clear its
  score/combo/hit state, resets the countdown accumulator to `0.0`, clears the
  cached finish time, and sets state to `IDLE`. The presence of `demo_source`
  selects a demo run (post-countdown state `DEMO`); absence selects a normal run
  (`PLAYING`). `load` may be called again to reset to a fresh run (possibly a
  different chart); the `scoring.reset(chart)` call is what makes that sound.

### State machine

| From | Trigger | To | Side effect |
|---|---|---|---|
| `IDLE` | `start()` | `COUNTDOWN` | reset countdown accumulator |
| `COUNTDOWN` | `update`, accumulator ≥ `countdown_ms` | `PLAYING` / `DEMO` | `clock.play()` |
| `PLAYING`/`DEMO` | `update`, `current_ms ≥ total+padding` | `FINISHED` | `clock.stop()` |
| `PLAYING`/`DEMO` | `pause()` | `PAUSED` | `clock.pause()` |
| `PAUSED` | `resume()` | `PLAYING` / `DEMO` (prior) | `clock.resume()` |

`COUNTDOWN → PLAYING` vs `COUNTDOWN → DEMO` is decided by whether a `demo_source`
was supplied to `load`.

### `start()`

Precondition: a chart is loaded and state is `IDLE`. Transitions to `COUNTDOWN`
and resets the countdown accumulator to `0.0`. Does **not** start the clock —
the clock only runs once play begins, so the countdown is timed by the `dt_ms`
values fed to `update`.

### `update(dt_ms)`

Single per-frame entry point. `dt_ms` is the wall time elapsed since the previous
frame (caller-supplied, e.g. from the pygame clock).

- `IDLE`, `PAUSED`, `FINISHED`: no-op.
- `COUNTDOWN`: `_countdown_elapsed += dt_ms`. When `_countdown_elapsed ≥
  countdown_ms`: call `clock.play()` once and transition to `DEMO` if a
  `demo_source` is set, else `PLAYING`. (The clock's own zero starts here, so the
  countdown overshoot is not carried into the play clock.)
- `PLAYING`:
  1. `now = clock.current_ms()`
  2. `scoring.tick(now)`
  3. if `now ≥ chart.total_duration_ms + end_padding_ms`: cache
     `_finished_ms = now`, then `clock.stop()`, state → `FINISHED`.
- `DEMO`: as `PLAYING`, but before `scoring.tick` it pulls demo input:
  1. `now = clock.current_ms()`
  2. for `sig in demo_source.tick(now)`: `scoring.register_hit(sig.lane, sig.time_ms)`
  3. `scoring.tick(now)`
  4. finish check as `PLAYING` (cache `_finished_ms` before `clock.stop()`).

The finish time is cached **before** `clock.stop()` because `AudioPlayer.stop()`
(§8) does not guarantee it preserves the final position — a future `stop()` may
reset the clock to 0. `current_ms()` reads the cached value in `FINISHED` so the
renderer's scroll position does not snap backward at the end of the run.

Demo's perfect timing comes from forwarding each signal's own `sig.time_ms`
(which equals the note's `time_ms`), not the wall clock — so demo hits always
land inside the PERFECT window regardless of frame cadence.

### `handle_input(lane)`

Forwards to `scoring.register_hit(lane, self.current_ms())` **only** in
`PLAYING`. No-op in every other state — notably `DEMO` (real input is ignored
during demo playback), `COUNTDOWN`, `PAUSED`, `IDLE`, `FINISHED`.

The engine is the timestamp authority: `handle_input` takes only the `lane` and
stamps the hit with `self.current_ms()` (which is `clock.current_ms()` in
`PLAYING`). It deliberately does **not** accept a caller-supplied `time_ms`,
because raw pygame `KEYDOWN` and rtmidi timestamps are not in the audio/chart
clock domain; trusting them would corrupt the ±35 ms judgments. DESIGN.md §8
establishes the same contract ("scoring always uses `audio.current_ms()`"). The
small, *consistent* latency between physical press and the frame that calls
`handle_input` is acceptable and is the same for every input; per-source
timestamp translation is out of scope. The §11/§12 input handlers still produce
`InputSignal` for lane extraction, but the wiring calls `engine.handle_input(lane)`
and lets the engine own the time.

### `pause()` / `resume()`

- `pause()`: from `PLAYING` or `DEMO` only → `PAUSED`, calling `clock.pause()`.
  The engine records which state it paused from. Called in any other state: no-op.
- `resume()`: from `PAUSED` only → the recorded prior state (`PLAYING`/`DEMO`),
  calling `clock.resume()`. Called in any other state: no-op.

Redundant calls (`pause()` while already paused, `resume()` while playing) are
deliberately no-ops so a UI that double-fires the toggle cannot crash the engine.

### `current_ms()` — scroll-position authority

The single source the renderer reads to position notes
(`note_z = (note.time_ms - current_ms()) * UNITS_PER_MS`, DESIGN.md §13):

| State | `current_ms()` |
|---|---|
| `IDLE` | `-countdown_ms` |
| `COUNTDOWN` | `_countdown_elapsed - countdown_ms` (negative; rises toward 0) |
| `PLAYING` / `DEMO` / `PAUSED` | `clock.current_ms()` |
| `FINISHED` | `_finished_ms` (cached at finish, before `clock.stop()`) |

Negative pre-roll during `IDLE`/`COUNTDOWN` parks the first notes off-screen and
scrolls them in during the 3-2-1, so the board is already moving when play
begins. `PAUSED` freezes because the clock is paused. `FINISHED` returns the
cached finish time so a position-resetting `clock.stop()` cannot snap the
renderer's scroll back to 0.

### `countdown_value()`

For the HUD's "3 / 2 / 1" display. Defined only meaningfully in `COUNTDOWN`:
`ceil((countdown_ms - _countdown_elapsed) / 1000)`, clamped to `[0,
ceil(countdown_ms/1000)]`. Returns `0` outside `COUNTDOWN`.

### `is_demo()` / `is_finished()` / `state`

- `is_demo()`: True when the active play state is demo — `state == DEMO`, or
  `state == PAUSED` with a demo prior state. Stays stable across a pause.
- `is_finished()`: `state == FINISHED`.
- `state`: read-only property exposing the current `GameState`.

### Finish semantics: chart tail, not audio completion

The run ends at `chart.total_duration_ms + end_padding_ms` — when the last note's
hit window has fully closed plus a short tail — **not** when the audio file
finishes. This is an intentional change from DESIGN.md §9's "all notes resolved
and audio done" wording (chosen during brainstorming), and §9 is updated to
match.

Rationale: the gameplay-meaningful end is when no note can still be judged.
`end_padding_ms` (default 2000) covers the last note resolving plus a brief
ring-out. Tying finish to audio length instead would make the `Clock` Protocol
carry a duration contract it otherwise doesn't need, and would stall on a results
screen through a long instrumental outro. Tradeoff: a song whose audio outro runs
well past the last note will have its audio stopped at the chart tail. If a song
ever needs its full outro, raise `end_padding_ms` for that run — the knob is
per-engine. No audio-duration contract is added to `Clock` in v1.

| Condition | Behavior |
|---|---|
| `start()` or `update()` before `load()` | `RuntimeError` |
| `start()` when state is not `IDLE` | `RuntimeError` |
| `pause()` outside `PLAYING`/`DEMO` | no-op |
| `resume()` outside `PAUSED` | no-op |
| `handle_input` outside `PLAYING` | no-op |

`start()`/`update()` before `load()` is a programming error (the run lifecycle
was misused) and fails loudly. Redundant pause/resume/input are expected at
runtime and are absorbed.

## Test plan

New files: `tests/test_game_engine.py`, `tests/test_input_signal.py`. Tests use
fakes for the three collaborators.

### Fakes

- `FakeClock`: scriptable `current_ms` (settable by the test); records the call
  order of `play`/`pause`/`resume`/`stop`; `is_playing` reflects the last call.
- `FakeScoring`: records `reset(chart)` calls, `register_hit(lane, time_ms)`
  calls, and `tick(now)` calls.
- `FakeDemoSource`: returns a scripted `list[InputSignal]` per `tick`, and records
  the `now` it was called with.

### `InputSignal` (`tests/test_input_signal.py`)

- Fields `lane`, `time_ms` exist and round-trip.
- Equality of two identical signals.

### Lifecycle & state machine (`tests/test_game_engine.py`)

- Initial state is `IDLE`; `is_finished()` False, `is_demo()` False.
- `start()` before `load()` → `RuntimeError`.
- `update()` before `load()` → `RuntimeError`.
- After `load`, state is `IDLE`; `start()` → `COUNTDOWN`; clock.play **not** called.
- `load(chart)` calls `scoring.reset(chart)` exactly once with that chart.
- A second `load(chart2)` calls `scoring.reset(chart2)` and returns state to `IDLE`.
- `start()` when already in `COUNTDOWN`/`PLAYING` → `RuntimeError`.

### Countdown

- `update(dt)` accumulates: with `countdown_ms=3000`, `update(1000)` ×2 keeps
  state `COUNTDOWN` and clock.play uncalled.
- Crossing the threshold (`update(1000)` ×3, or a single `update(3000)`)
  transitions to `PLAYING` (no demo source) and calls `clock.play()` exactly once.
- With a demo source loaded, the same crossing transitions to `DEMO`.
- `countdown_value()` returns 3, then 2, then 1 as the accumulator advances;
  returns 0 outside `COUNTDOWN`.
- `current_ms()` is `-countdown_ms` in `IDLE`, negative and rising in `COUNTDOWN`,
  reaching ~0 at the threshold.

### Playing

- In `PLAYING`, each `update` calls `scoring.tick(clock.current_ms())`.
- `handle_input(lane)` in `PLAYING` forwards one `register_hit(lane, now)` where
  `now == clock.current_ms()` at call time (set `FakeClock.current_ms`, call
  `handle_input`, assert the recorded time equals that value — the caller passes
  no time).
- `handle_input` is a no-op in `COUNTDOWN`, `PAUSED`, `DEMO`, `IDLE`, `FINISHED`
  (no `register_hit` recorded).

### Demo

- In `DEMO`, `update` calls `demo_source.tick(now)` and forwards every returned
  signal to `scoring.register_hit` with the signal's `lane`/`time_ms`.
- In `DEMO`, `update` still calls `scoring.tick(now)`.
- `is_demo()` is True in `DEMO` and remains True after `pause()` (state `PAUSED`).

### Finish

- With `total_duration_ms=5000`, `end_padding_ms=2000`: `FakeClock.current_ms=6999`
  stays `PLAYING`; `=7000` transitions to `FINISHED` and calls `clock.stop()`.
- `is_finished()` True only in `FINISHED`.
- `update` in `FINISHED` is a no-op (no further `scoring.tick`).
- Finish time is cached: a `FakeClock` whose `stop()` resets `current_ms` to 0
  still leaves `engine.current_ms() == 7000` after finishing (the cached
  `_finished_ms`, not the post-stop clock value).

### Pause / resume

- `pause()` from `PLAYING` → `PAUSED`, calls `clock.pause()`; `current_ms()` returns
  the (frozen) `clock.current_ms()`.
- `resume()` from `PAUSED` → `PLAYING`, calls `clock.resume()`.
- `pause()` from `DEMO` → `PAUSED`; `resume()` returns to `DEMO` (not `PLAYING`).
- Redundant `pause()` (already `PAUSED`) and `resume()` (in `PLAYING`) are no-ops:
  no extra `clock.pause`/`clock.resume` recorded.

## Files affected

| File | Change |
|---|---|
| `src/input/__init__.py` | New (empty) |
| `src/input/signal.py` | New — `InputSignal` dataclass |
| `src/game/engine.py` | New — `GameState`, Protocols, `GameEngine` |
| `tests/test_input_signal.py` | New |
| `tests/test_game_engine.py` | New |
| `ai-working-log/DESIGN.md` | §9: replace internal `AudioPlayer`/`DemoPlayer` construction + `audio_path` with injected `Clock`/`Scoring`/`DemoSource` (incl. `Scoring.reset(chart)`); `handle_input(lane)` (engine stamps the time, no caller `time_ms`); replace "all notes resolved and audio done" with chart-tail finish (`total_duration_ms + END_PADDING_MS`); document dt-accumulator countdown and `current_ms()` scroll semantics (negative pre-roll, cached finish time) |
| `TRACKING.md` | Mark Phase 2.4 status; session log entry |

## Related design issues (still deferred)

Unchanged from the chart-builder spec; none are resolved here:

- §13: HUD-over-OpenGL upload-as-texture pattern.
- §6/§11/§12: hold-note press/release semantics — `InputSignal` has no `release`
  type; `Scoring.register_hit` is press-only. This engine forwards presses only.
- Migration map for legacy root-level modules (`midi/`, `ui/`, `KeyMapper.py`,
  the empty `Mp3Player/`).
