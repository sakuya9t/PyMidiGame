# Chart Builder — Design Spec

**DESIGN.md reference:** Step 1.4 (Phase 1 — MIDI Foundation)
**TRACKING.md reference:** Phase 2.3
**Date:** 2026-05-04

## Goal

Convert a parsed `list[NoteEvent]` (output of `MidiParser.parse`) plus a `KeyboardClass` (output of `classify`) into a sorted `Chart` object that the rendering and scoring systems can consume. This is the last piece of the MIDI ingestion pipeline before gameplay can use the data.

## Scope

In scope:
- `src/game/chart.py` (creates the `src/game/` package).
- Two dataclasses: `Note`, `Chart`.
- One class: `ChartBuilder` with a single `@classmethod build()`.
- Both lane-assignment modes: `"midi"` (1:1) and `"pc"` (compressed to 8 lanes).
- A small adjacent change to `src/midi/classifier.py`: out-of-range MIDIs are rejected with `ValueError` instead of silently mapped to 88-key. The game supports up to 88 keys, so any MIDI with notes outside `[21, 108]` is unsupported and must fail at load time.

Out of scope:
- Chord grouping. Notes that share a `time_ms` end up adjacent in the sorted output, but `ChartBuilder` does not produce a `Chord` type or assign chord IDs. Scoring can revisit this when the data shape needs revisiting.
- Hold-note release signaling. `Note.duration_ms` flows through unchanged; the press/release pipeline (input handlers, scoring) is a separate concern.

## Data structures

```python
# src/game/chart.py
from __future__ import annotations
from dataclasses import dataclass

from src.midi.classifier import KeyboardClass


@dataclass
class Note:
    """A single playable note in chart coordinates."""
    lane: int            # 0-indexed lane within the chart's lane_count
    midi_note: int       # Original MIDI pitch (preserved for hold/release matching)
    time_ms: float       # Absolute hit time in milliseconds (chart clock)
    duration_ms: float   # Hold duration; 0.0 for tap notes
    hit: bool = False
    missed: bool = False


@dataclass
class Chart:
    """A complete playable chart."""
    notes: list[Note]              # Non-decreasing by time_ms; chord notes adjacent
    kb_class: KeyboardClass
    mode: str                      # "midi" or "pc"
    lane_count: int                # kb_class.key_count for "midi"; 8 for "pc"
    total_duration_ms: float       # max(time_ms + duration_ms); 0.0 if empty
```

`Chart.lane_count` is not in DESIGN.md §4 but is added because the renderer and lane layout need it directly. Deriving it from `(mode, kb_class)` in every consumer would duplicate logic.

## Algorithm

```python
ChartBuilder.build(events: list[NoteEvent], kb_class: KeyboardClass, mode: str) -> Chart:

    if mode not in ("midi", "pc"):
        raise ValueError(f"unknown mode {mode!r}; expected 'midi' or 'pc'")

    # kb_class declares the supported MIDI range. Any event outside it is
    # a contract violation. The classifier should reject these upstream;
    # we enforce the contract defensively here regardless of mode.
    for e in events:
        if not (kb_class.midi_low <= e.note <= kb_class.midi_high):
            raise ValueError(
                f"MIDI note {e.note} is outside the {kb_class.name} range "
                f"[{kb_class.midi_low}, {kb_class.midi_high}]"
            )

    lane_count = kb_class.key_count if mode == "midi" else 8

    if not events:
        return Chart(notes=[], kb_class=kb_class, mode=mode,
                     lane_count=lane_count, total_duration_ms=0.0)

    if mode == "midi":
        notes = [
            Note(lane=e.note - kb_class.midi_low, midi_note=e.note,
                 time_ms=e.time_ms, duration_ms=e.duration_ms)
            for e in events
        ]

    else:  # mode == "pc"
        song_min = min(e.note for e in events)
        song_max = max(e.note for e in events)
        if song_min == song_max:
            notes = [
                Note(lane=0, midi_note=e.note,
                     time_ms=e.time_ms, duration_ms=e.duration_ms)
                for e in events
            ]
        else:
            span = song_max - song_min
            notes = [
                Note(lane=int((e.note - song_min) / span * (lane_count - 1) + 0.5),
                     midi_note=e.note,
                     time_ms=e.time_ms, duration_ms=e.duration_ms)
                for e in events
            ]

    notes.sort(key=lambda n: n.time_ms)
    total = max(n.time_ms + n.duration_ms for n in notes)
    return Chart(notes=notes, kb_class=kb_class, mode=mode,
                 lane_count=lane_count, total_duration_ms=total)
```

### MIDI mode

Direct subtraction: `lane = note - kb_class.midi_low`. The range check above ensures every note falls in `[0, lane_count)`.

### PC mode

Notes are compressed into 8 lanes (matching `PC_KEY_MAP = [A S D F J K L ;]`) by linear interpolation against the actual song range:

- `song_min` always maps to lane 0.
- `song_max` always maps to lane 7.
- Intermediate pitches fall on a uniform scale between the anchors.
- A song with a single distinct pitch collapses to lane 0.

This keeps the chart visually anchored at both screen edges regardless of the song's pitch range. A two-pitch song uses lanes 0 and 7; a song with many distinct pitches fills all 8 lanes.

The rounding uses `int(x + 0.5)` rather than Python's built-in `round()`. Python's `round()` applies banker's rounding (half to even), which would systematically skip odd-numbered lanes whenever `(offset / span) * 7` lands on `.5`. For example, with `kb_class=49key` and a song spanning `[60, 74]`, note 65 yields `5/14 * 7 = 2.5` exactly — `int(2.5 + 0.5) = 3` (correct), but `round(2.5) = 2` (banker's, asymmetric).

### Sort order

Stable sort by `time_ms`. Notes with identical timestamps retain their input order. If a deterministic tie-breaker is needed downstream (snapshot tests, replay), the key can be extended to `(time_ms, lane, midi_note)` without affecting correctness.

### `total_duration_ms`

`max(n.time_ms + n.duration_ms for n in notes)`. This is the true end of the last sounding note, which may not be the last note's start time if a long hold note ends after a later short note.

## Error policy

| Condition | Behavior |
|---|---|
| `mode` is not `"midi"` or `"pc"` | `ValueError` |
| `events == []` | Returns empty `Chart` |
| Any event note outside `[kb_class.midi_low, kb_class.midi_high]` (either mode) | `ValueError` |
| PC mode, all events same pitch | All notes → lane 0 |

## Adjacent change: classifier rejection

`src/midi/classifier.py` currently returns `88key` as a fallback when no class fits. This is replaced with a `ValueError`:

```python
# Before:
return _KEYBOARD_CLASSES[-1]

# After:
raise ValueError(
    f"MIDI note range [{min_note}, {max_note}] exceeds the supported "
    f"88-key piano range [21, 108]. The game does not support charts "
    f"with notes outside this range."
)
```

Existing tests in `tests/test_midi_classifier.py` that rely on the fallback are updated.

## Test plan

New file: `tests/test_chart_builder.py`. Tests use synthetic `NoteEvent` lists; the parser's own coverage handles real MIDI parsing.

### MIDI mode

- 1:1 mapping anchors: `note=48` with `kb_class=25key` → lane 0; `note=72` with `kb_class=25key` → lane 24.
- `lane_count == kb_class.key_count`.
- All produced lanes within `[0, lane_count)`.

### PC mode

- `lane_count == 8`.
- 12-semitone span `[60, 71]`: note 60 → lane 0, note 71 → lane 7.
- Edge anchoring across multiple ranges (12, 20, 60 semitones): `song_min` always maps to lane 0; `song_max` always maps to lane 7.
- Narrow-range song (notes 60 and 61): note 60 → lane 0, note 61 → lane 7.
- Single-pitch song: every note → lane 0.
- Mid-range pitch lands as expected: span `[60, 71]`, note 65 → `int(5/11 * 7 + 0.5) = 3` → lane 3.
- Rounding behavior: span `[60, 74]`, note 65 → lane 3 (half-up), not lane 2 (banker's). This test would fail under `round()`.

### Range validation

- MIDI mode, note above `kb_class.midi_high` → `ValueError`.
- MIDI mode, note below `kb_class.midi_low` → `ValueError`.
- PC mode, note above `kb_class.midi_high` → `ValueError`.
- PC mode, note below `kb_class.midi_low` → `ValueError`.

### Sorting

- Input out of time order: output is non-decreasing by `time_ms`.
- Ties: two events with identical `time_ms` retain their input order.

### `total_duration_ms`

- Tap-only chart, last note at `t=5000ms, duration=0` → `total = 5000`.
- Last note has duration: last note `t=5000, duration=2000` → `total = 7000`.
- A non-last note has the longest end time: note A at `t=4000, duration=3000` (ends at 7000), note B at `t=5000, duration=0` (ends at 5000) → `total = 7000`.
- Empty chart → `total = 0.0`.

### Modes and inputs

- Invalid mode (`"keyboard"`, `""`) → `ValueError`.
- Empty events: returns `Chart` with correct `lane_count` and `total_duration_ms = 0.0`.

### Classifier rejection (in `tests/test_midi_classifier.py`)

- Notes containing MIDI 109 (above 108) → `ValueError`.
- Notes containing MIDI 20 (below 21) → `ValueError`.
- Existing fallback test updated to expect `ValueError`.

## Files affected

| File | Change |
|---|---|
| `src/game/__init__.py` | New (empty) |
| `src/game/chart.py` | New |
| `src/midi/classifier.py` | Replace fallback with `ValueError` |
| `tests/test_chart_builder.py` | New |
| `tests/test_midi_classifier.py` | Update fallback test |
| `ai-working-log/DESIGN.md` | §4 ChartBuilder: remove chord-grouping line; replace "equal-width bins" with "linear interpolation". §2 Classifier: specify rejection on out-of-range. |
| `TRACKING.md` | Mark Phase 2.3 status |

## Related design issues (deferred)

The codex review of DESIGN.md surfaced four concerns that are real but orthogonal to Chart Builder. They will be addressed when the relevant phases come up:

- §13: HUD-over-OpenGL pattern — `display.blit()` does not work in `OPENGL | DOUBLEBUF` mode. The HUD surface needs to be uploaded as a GL texture and drawn as a screen-space quad.
- §6/§11/§12: hold-note press/release semantics gap — `InputSignal` has no release type, and `ScoringEngine.register_hit` is press-only.
- §9: stale 2D Y-pixel formula in `GameEngine.update`, leftover from the recent `Note.y` removal.
- Migration map for legacy modules at the repo root (`midi/`, `ui/`, `KeyMapper.py`, the empty `Mp3Player/`, etc.).
