# MidiMania — Design Document

> Living design notes: **strategy, decisions, and workflows**. Concrete interfaces
> (dataclass fields, method signatures, exact constants) live in the code under
> `src/` and are not restated here. Per-feature design specs with the detailed
> reasoning are in [`specs/`](specs/).

## Overview

MidiMania is a cross-platform, DJmax-style rhythm game where note patterns fall
from a vanishing point and grow toward a judgment bar; the player presses the
matching key as each note arrives. Patterns are auto-generated from a `.mid` file
(plus optional paired audio), and play works with either a PC keyboard or a
physical MIDI keyboard.

**Input modes:**
- **PC Keyboard** — always available; the song's pitch range is compressed onto 9
  lanes (`A S D F Space J K L ;`).
- **MIDI Keyboard** — available once a device is detected and calibrated; 1:1
  note → lane, so chords stay distinct.
- **Demo** — the game auto-plays at perfect timing (100% / S every run), for
  previewing a song or verifying setup with no input device.

When no MIDI device is present, the menu defaults to **PC Keyboard**; Demo is an
explicit selectable option, never the forced path.

---

## Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.10+ | Cross-platform, rich MIDI ecosystem |
| Window / audio / events | pygame 2.x | Cross-platform window, mixer, event loop, surface blitting |
| In-game 3D renderer | PyOpenGL | Perspective camera gives the DJmax vanishing-point look |
| HUD / text overlay | pygame surfaces composited over GL as a textured quad | Fast, no GL font textures; replaces `glDrawPixels` |
| MIDI file parsing | mido | Pure-Python, reliable |
| MIDI device input | python-rtmidi | Native MIDI I/O on Win/Mac/Linux |
| Audio playback | pygame.mixer | Built-in; MP3/OGG/WAV/FLAC |
| Packaging (future) | PyInstaller | Single-binary distribution per OS |

**Runtime:** Python 3.10+, an OpenGL driver, pygame system deps, and (for rtmidi
on Linux) the platform MIDI backend.

---

## Development Workflow

- **brainstorm → design spec → TDD → milestone commit.** Each non-trivial feature
  gets a dated spec in [`specs/`](specs/) before code; that spec carries the
  detailed interface design so this document doesn't have to.
- Work proceeds in **per-phase branches**, one commit per milestone.
- **Tests run headless** under SDL dummy video/audio drivers, so the full core and
  UI flow are provably correct without a display or audio device. The handful of
  **GL smoke tests** need a real OpenGL context and auto-skip under the dummy
  driver / CI.
- External backends (rtmidi, pygame.mixer, the MIDI synth) sit behind **injectable
  seams with lazy imports**, so modules import and tests run with no hardware.
- Entry point: `python mania.py` opens the song-select menu over `songs/`;
  `python mania.py SONG.mid` plays one chart directly.

---

## Architecture & Key Decisions

Packages: `src/midi` (parse/classify/device), `src/game` (chart/engine/scoring/
demo), `src/audio` (player/synth), `src/input` (signal/midi adapter), `src/ui`
(renderer/menu/results/midi_setup + GL helpers). `InputSignal(lane, time_ms)` is
the shared input currency across PC, MIDI, and demo sources.

**MIDI parsing & classification** (`src/midi/parser.py`, `classifier.py`)
- Support type 0/1 only; **reject type 2** (independent per-track timelines).
  Build a tempo map from all `set_tempo` events and convert ticks → ms with
  mid-file tempo changes; `note_on` vel>0 starts a note, `note_off`/vel-0 ends it.
- Classify to the **smallest physical keyboard that covers `[min, max]`**:

  | Class | Keys | MIDI range |
  |---|---|---|
  | 25key | 25 | 48–72 (C3–C5) |
  | 32key | 32 | 41–72 (F2–C5) |
  | 37key | 37 | 41–77 (F2–F5) |
  | 49key | 49 | 36–84 (C2–C6) |
  | 61key | 61 | 36–96 (C2–C7) |
  | 88key | 88 | 21–108 (A0–C8) |

  Notes outside `[21, 108]` raise `ValueError` (v1 caps at 88 keys; no silent
  88-key fallback). MIDI-mode lane = `note − midi_low`.

**Chart building** (`src/game/chart.py`)
- **MIDI mode:** 1:1, `lane = note − midi_low`, `lane_count = key_count`.
- **PC mode:** the song's pitch range is compressed onto **9 lanes** by linear
  interpolation (lowest → lane 0, highest → lane 8), half-up rounding
  (`int(x + 0.5)`); a single-pitch song collapses to the center lane.
- Validate every note against the class range (both modes); stable-sort by
  `time_ms`; `total_duration_ms = max(time_ms + duration_ms)`.

**Timing model** (the spine of the game)
- The **audio clock is the single timing authority** (`AudioPlayer.current_ms()`),
  driven by an *injectable wall clock* (not the backend's position query),
  excluding paused time, and applying `AUDIO_OFFSET_MS` (manual A/V calibration).
  Scoring never reads raw `perf_counter`.
- The **engine stamps input timestamps itself** from the audio clock, so
  heterogeneous pygame/rtmidi event times can't corrupt the ±35 ms judgments.

**Scoring** (`src/game/scoring.py`) — game-design parameters
- Hit windows **±35 / ±75 / ±120 ms** → PERFECT / GREAT / GOOD; else MISS.
- `base = 1_000_000 / total_notes`, scaled ×1.0 / 0.7 / 0.4; a MISS resets combo.
- `accuracy = (perfect + great) / total`; ranks **S ≥98% · A ≥90% · B ≥75% ·
  C ≥60% · D** below.
- `register_hit` resolves the **nearest unresolved note in the lane** within GOOD;
  a stray press (no note in range) is a MISS that consumes no note and doesn't
  reset combo. `tick()` is the **authoritative miss**: a note past its GOOD window
  is marked missed and resets combo. Scoring owns each note's `hit/missed` flag.

**Game engine** (`src/game/engine.py`)
- State machine `IDLE → COUNTDOWN → PLAYING/DEMO → FINISHED`, with `PAUSED` off the
  play states (pause preserves whether the run is a demo).
- Collaborators (`Clock`, `Scoring`, `DemoSource`) are **injected via structural
  Protocols** — the engine never constructs them. This keeps "drive the state
  machine" decoupled from audio/scoring/demo and lets the engine be built and
  tested before those deps exist.
- Countdown is timed by a **`dt_ms` accumulator** (the clock isn't running
  pre-play). The run **finishes at `chart.total_duration_ms + end_padding`**
  (chart tail, not audio-file EOF) and the finish time is cached, so a
  position-resetting `clock.stop()` can't snap the scroll back to 0.

**Input** (`src/input/`, `src/midi/device.py`, `src/ui/midi_setup.py`)
- **PC:** a keymap binds pygame key codes to lanes.
- **MIDI device:** rtmidi behind an injectable backend (lazy import) →
  headless-testable. Uses **frame polling** (drain `get_message()` each frame),
  not a background-thread callback queue — simpler and thread-safe; a callback
  upgrade for tighter timing is noted future work.
- **MIDI adapter:** `note_on → lane = note − midi_low`; out-of-range and
  `note_off` are ignored.
- **Calibration:** a MIDI port can't report its key count, so the setup screen has
  the player press the **lowest + highest** key — this both confirms the link (live
  echo) and measures the span, which then limits the selectable keys-mode.

**Rendering** (`src/ui/`) — OpenGL vanishing-point, texture-first
- One persistent `DOUBLEBUF | OPENGL` window: the 3D perspective scene is drawn,
  then **every 2D layer (menu, HUD, countdown, results) is composited on top as a
  fullscreen textured quad** (`gl_overlay.py`), retiring `glDrawPixels`.
- Notes live in world space via `note_z = (note.time_ms − current_ms) ×
  UNITS_PER_MS`; the perspective projection maps Z → screen Y automatically.
  Placement math is **pure and unit-tested** (`geometry.py`).
- **Texture rendering is first-class:** the neon atlas is uploaded once and sampled
  by UV onto lane/note/hold/hit quads through a single `_textured_quad` primitive —
  the intended seam for future visual effects. `atlas.py` is the single source of
  UV truth; a flat-color fallback covers a missing atlas.
- HUD / countdown / results are drawn to a transparent pygame surface (`hud.py`)
  and presented over the GL frame.

**Menu, results, demo** (`src/ui/menu.py`, `results.py`, `src/game/demo.py`)
- The menu **scans `songs/`** (see Song Package Format) into a sorted list; a
  folder with no chart or an unparseable/over-range MIDI is **skipped, not fatal**.
  Keys: ↑↓ pick · ←→ input mode · K cycle keys-mode · M MIDI setup · Enter play ·
  Esc quit; after a song, Enter → menu, R → retry.
- MIDI mode is selectable only once a device is configured; keys-mode is limited to
  sizes that fit the measured span, and songs that don't fit are tagged unplayable
  in MIDI mode.
- The **demo player** pops every note whose time has arrived as a perfect
  `InputSignal`, routed through the normal scoring/effects path → 1,000,000 / S
  every run; the results screen adds a DEMO banner.

**Audio fallback** (`src/audio/`)
- Audio precedence: an explicit `--audio` file → a produced track paired with the
  chart by name → else a **temporary WAV synthesized from the MIDI**
  (`synth.py`). So a song needs no shipped audio to be playable.

---

## Data Flow

```
[MIDI file]                                   [Audio file | synth fallback]
    │                                                       │
 MidiParser ──► Classifier ──► ChartBuilder ──► Chart   AudioPlayer (Clock)
                                                   │           │
                                                   ▼           ▼
   InputSignal ─────────────────────────────►  GameEngine ◄────┘
        ▲                                          │
  ┌─────┴───────┬──────────────┐              ScoringEngine
 PC keys   MIDI adapter    DemoPlayer              │
              ▲                                     ▼
         MIDI device                            Renderer ──► GL display + HUD
```

---

## Input Mode Comparison

| Feature | PC Keyboard | MIDI Keyboard |
|---|---|---|
| Lane count | 9 (compressed) | Matches keyboard size (25–88) |
| Note mapping | Notes binned into 9 lanes | 1:1 note → lane |
| Key label | `A S D F Space J K L ;` | Note names |
| Chord accuracy | No — collisions collapse | Yes — each key distinct |
| Recommended for | Casual play | Authentic experience |

---

## Song Package Format

```
songs/<name>/
├── chart.mid                 # required (or the first *.mid in the folder)
├── meta.json                 # optional: { "title", "artist", "bpm" }
└── <name>.ogg|.mp3|.wav|.flac  # optional produced audio; else a synth preview
```

`meta.json` fields are all optional; an absent `title` falls back to the
prettified folder name.

---

## Remaining / Future Work

Not yet built (Phase 5 polish and beyond):
- **Hit effects** — per-grade color flash / expanding ring at the hit zone, hold-
  note glow, column flash on press.
- **HUD polish** — combo pop animation.
- **Large-keyboard viewport (49key+)** — a fixed scrolling window of ~25 lanes
  auto-centered on recently active lanes, with a miniature full-range strip
  highlighting the visible window (keeps lane width readable at 88 keys).
- **Cross-platform verification** on Windows/macOS/Linux and **PyInstaller
  packaging**.

## Out of Scope (v1)

Online leaderboards · skins/themes · multiplayer · note editor · video
backgrounds · automatic A/V offset calibration (the manual `AUDIO_OFFSET_MS` is
sufficient for v1).
