# MidiMania — Design Document

## Overview

MidiMania is a cross-platform, DJmax-style rhythm game where note patterns fall from the top of the screen and players press the corresponding key as each note reaches the judgment bar. Patterns are auto-generated from MIDI files, and the game supports both PC keyboard and physical MIDI keyboard input.

**Input modes:**
- **PC Keyboard** — always available; up to 8 lanes mapped to `A S D F J K L ;`.
- **MIDI Keyboard** — available when a device is detected at startup.
- **Demo Mode** — the game plays itself with perfect timing, useful for previewing a song or verifying setup without any input device.

If no MIDI device is detected at startup, the song selection screen defaults to **PC Keyboard** mode. Demo Mode is offered as an explicit option, not the forced path.

---

## Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Cross-platform, rich MIDI ecosystem |
| Window / audio / events | pygame 2.x | Cross-platform window, mixer, event loop, surface blitting |
| In-game 3D renderer | PyOpenGL (OpenGL 2.1) | Perspective camera gives DJmax vanishing-point look; already working in old codebase |
| HUD / text overlay | pygame surfaces blitted over GL | Fast, no GL font textures needed; replaces `glDrawPixels` |
| MIDI file parsing | mido | Pure-Python, reliable MIDI parsing |
| MIDI device input | python-rtmidi | Native MIDI I/O on Win/Mac/Linux |
| Audio playback | pygame.mixer | Built-in, supports MP3/OGG/WAV |
| Packaging | PyInstaller | Single-binary distribution per OS |

**Runtime requirements:** Python 3.11+, PortAudio (for rtmidi on Linux), OpenGL 2.1 driver (available on all target platforms), pygame system deps.

---

## Directory Structure

```
midimania/
├── main.py                    # Entry point
├── config.py                  # Global constants and defaults
├── requirements.txt
├── DESIGN.md
│
├── songs/                     # Song library (user-managed)
│   └── <song_name>/
│       ├── audio.mp3          # Audio file (MP3/OGG/WAV)
│       ├── chart.mid          # Pattern-source MIDI file
│       └── meta.json          # Optional: title, artist, BPM override
│
├── assets/
│   ├── fonts/
│   └── sfx/                   # Hit sound effects
│
└── src/
    ├── midi/
    │   ├── __init__.py
    │   ├── parser.py          # MIDI file → NoteEvent list
    │   ├── classifier.py      # Note range → keyboard size class
    │   └── device.py          # Real-time MIDI device I/O
    │
    ├── game/
    │   ├── __init__.py
    │   ├── chart.py           # Chart: NoteEvent list → Lane/Note objects
    │   ├── note.py            # Note data class
    │   ├── lane.py            # Lane layout and state
    │   ├── engine.py          # Game loop, state machine
    │   ├── scoring.py         # Hit windows, score, combo
    │   └── demo.py            # DemoPlayer: auto-hits for demo mode
    │
    ├── audio/
    │   ├── __init__.py
    │   └── player.py          # Audio file playback + sync
    │
    ├── input/
    │   ├── __init__.py
    │   ├── keyboard.py        # PC keyboard → lane signals
    │   └── midi_input.py      # MIDI device → lane signals
    │
    └── ui/
        ├── __init__.py
        ├── renderer.py        # In-game renderer (lanes, notes, HUD)
        ├── menu.py            # Song selection screen
        ├── results.py         # End-of-song results screen
        └── effects.py         # Particle / hit effects
```

---

## Module Reference

### 1. `src/midi/parser.py` — MIDI File Parser

**Purpose:** Read a `.mid` file and produce a flat, time-absolute list of note events.

**Key class: `MidiParser`**

```
MidiParser.parse(path: str) -> list[NoteEvent]
```

**`NoteEvent` dataclass:**

```python
@dataclass
class NoteEvent:
    note: int          # MIDI note number (0–127)
    time_ms: float     # Absolute start time in milliseconds
    duration_ms: float # Note duration in milliseconds
    channel: int       # MIDI channel (0–15)
    velocity: int      # 0–127
```

**Implementation notes:**
- Use `mido.MidiFile` to read the file.
- Support `type 0` (single track) and `type 1` (multi-track sync) only. Raise `ValueError` for `type 2`, since each track has an independent timeline.
- Walk through all tracks, accumulate absolute ticks per track, then use the `set_tempo` map to convert ticks → milliseconds.
- Treat `note_on` with velocity > 0 as a note start. Treat `note_off` and `note_on` with velocity 0 as the matching note end for the same channel+note, and emit one `NoteEvent` with the computed duration.

**Verification:** Unit test with a known MIDI file; assert note times match expected values (e.g., a 120 BPM MIDI with a note at beat 1 = 500 ms).

---

### 2. `src/midi/classifier.py` — Keyboard Size Classifier

**Purpose:** Determine the minimum physical keyboard size that covers all notes in a chart and define the MIDI-mode lane-to-note mapping. PC-mode lane compression is handled later by `ChartBuilder`.

**Standard keyboard sizes:**

| Class | Keys | MIDI range | Notes |
|---|---|---|---|
| `25key` | 25 | 48–72 (C3–C5) | 2 octaves |
| `32key` | 32 | 41–72 (F2–C5) | 2.5 octaves |
| `37key` | 37 | 41–77 (F2–F5) | 3+ octaves |
| `49key` | 49 | 36–84 (C2–C6) | 4 octaves |
| `61key` | 61 | 36–96 (C2–C7) | 5 octaves |
| `88key` | 88 | 21–108 (A0–C8) | Full piano |

**Key function: `classify(notes: list[NoteEvent]) -> KeyboardClass`**

- Finds `min_note` and `max_note` across all events.
- Iterates the class table (smallest first); returns the first class whose range covers `[min_note, max_note]`.
- If no class covers the range because the MIDI contains notes outside `[21, 108]`, raise `ValueError`. v1 supports up to 88-key charts.

**`KeyboardClass` dataclass:**

```python
@dataclass
class KeyboardClass:
    name: str          # "25key", "49key", etc.
    key_count: int     # Number of physical keys
    midi_low: int      # Lowest MIDI note in this class
    midi_high: int     # Highest MIDI note in this class
    lane_count: int    # Always == key_count; represents physical key count only
```

**Lane assignment (MIDI keyboard mode):**
```
lane = note - midi_low   # 0-indexed, left to right
```

**Verification:** Unit tests with crafted note sets, assert correct class is returned and lane indices are within range.

---

### 3. `src/game/note.py` — Note Data Class

**Purpose:** Represents a single falling note as chart/scoring state. Screen/world position is derived by the `Renderer` from `note.time_ms` and the current audio clock.

```python
@dataclass
class Note:
    lane: int              # Lane index (0-based)
    midi_note: int         # Underlying MIDI note number
    time_ms: float         # When it should be hit (audio time)
    duration_ms: float     # Hold duration (0 for tap notes)
    hit: bool = False      # Has been hit
    missed: bool = False   # Passed the bar without a hit
```

Renderer position formula: `note_z = (note.time_ms - current_ms) * UNITS_PER_MS`.

---

### 4. `src/game/chart.py` — Chart Builder

**Purpose:** Convert a `list[NoteEvent]` + `KeyboardClass` into a sorted `list[Note]` ready for the game engine.

**`ChartBuilder.build(events, kb_class, mode) -> Chart`**

- `mode`: `"midi"` for 1:1 note→lane mapping, or `"pc"` for 8-lane compression.
- Validate all events against `[kb_class.midi_low, kb_class.midi_high]`; out-of-range notes raise `ValueError`.
- In `"midi"` mode, use `lane = event.note - kb_class.midi_low`; `lane_count == kb_class.key_count`.
- In `"pc"` mode, map the song's lowest pitch to lane 0 and highest pitch to lane 7, with intermediate pitches placed by linear interpolation. A song with one distinct pitch uses lane 0. Rounding is half-up: `int(x + 0.5)`.
- Notes are sorted by `time_ms` (non-decreasing; stable, so simultaneous notes retain input order).

**`Chart` dataclass:**
```python
@dataclass
class Chart:
    notes: list[Note]
    kb_class: KeyboardClass
    mode: str                  # "midi" or "pc"
    lane_count: int            # kb_class.key_count for "midi"; 8 for "pc"
    total_duration_ms: float   # max(time_ms + duration_ms) across notes
```

**Verification:** Build a chart from a known MIDI, assert lane assignments and ordering are correct.

---

### 5. `src/game/lane.py` — Lane Layout

**Purpose:** Owns the visual geometry of each lane column.

**`LaneLayout`**

- `lane_count`: total lanes.
- `lane_width`: computed from screen width and lane count.
- `lane_x(index) -> int`: pixel X of the center of lane `index`.
- `bar_y`: Y pixel of the judgment bar (fixed, e.g. 88% down the screen).
- `spawn_y`: Y pixel where notes appear (top, e.g. -50 to allow off-screen spawn).
- `key_labels(mode, kb_class) -> list[str]`: human-readable label for each lane (note name in MIDI mode, keyboard key in PC mode).

**Visual layout rules:**
- Lane width is `screen_width / lane_count`, with a minimum of 14 px. Below 14 px, lanes would be unreadable, which cannot happen for any supported keyboard size at 1280px (88 keys × 14 px = 1232 px).
- **Large-keyboard viewport policy (49+ keys in MIDI mode):** v1 shows a fixed-width scrolling window of lanes (e.g. 25 lanes at ~51 px each on a 1280px screen). The viewport auto-centers on lanes that received input in the last ~1 second, and a miniature keyboard strip shows the full range with the visible window highlighted.
- Black vs white key lanes receive different colors to mirror piano layout.

---

### 6. `src/game/scoring.py` — Hit Detection and Scoring

**Purpose:** Evaluate input timing against expected note times and compute score.

**Hit windows** (relative to `note.time_ms`):

| Grade | Window |
|---|---|
| PERFECT | ±35 ms |
| GREAT | ±75 ms |
| GOOD | ±120 ms |
| MISS | outside window or key not pressed |

**Score formula (per note):**
```
base_score = 1_000_000 / total_notes
PERFECT -> base_score * 1.0
GREAT   -> base_score * 0.7
GOOD    -> base_score * 0.4
MISS    -> 0, combo reset
```

**`ScoringEngine`**
- `register_hit(lane, time_ms) -> Judgment`: match nearest unresolved note in lane within the largest window.
- `tick(current_time_ms)`: mark notes whose window has fully passed as MISS.
- Properties: `score`, `combo`, `max_combo`, `accuracy` (PERFECT+GREAT / total).

**Rank thresholds:**
- S: accuracy ≥ 98%
- A: ≥ 90%
- B: ≥ 75%
- C: ≥ 60%
- D: below 60%

**Verification:** Unit-test each judgment threshold, score accumulation, combo reset on miss.

---

### 7. `src/game/demo.py` — Demo Player

**Purpose:** Automatically generate perfect `InputSignal` events on behalf of the player, producing a flawless 100% score run used when no MIDI device is connected.

**`DemoPlayer`**

```python
class DemoPlayer:
    def __init__(self, chart: Chart, scoring: ScoringEngine):
        ...

    def tick(self, current_ms: float) -> list[InputSignal]:
        ...
```

**Behaviour:**
- On construction, builds a pending queue of all notes in the chart sorted by `time_ms`.
- Each call to `tick(current_ms)` pops every note whose `time_ms <= current_ms`. For each popped note it produces an `InputSignal(lane=note.lane, time_ms=note.time_ms)` — hitting at exactly the target time always falls inside the PERFECT window (±35 ms).
- For hold notes (duration > 0), a matching `release` signal is produced at `note.time_ms + note.duration_ms`.
- Returns the signals generated this tick. `GameEngine` feeds them through the normal scoring and hit-effect paths, so demo mode has the same visual feedback as real input.
- Signals are generated during `tick()` so pause/resume follows the normal game loop.

**Verification:** Load a 10-note chart; run `DemoPlayer.tick()` advancing time step by step; assert all 10 signals are generated and `ScoringEngine.score == 1_000_000` at end with `accuracy == 1.0`.

---

### 8. `src/audio/player.py` — Audio Player

**Purpose:** Load and play an audio file; provide a reliable current-time query that the scoring engine uses as its timing authority.

**`AudioPlayer`**
- `load(path: str)`: load file into `pygame.mixer`.
- `play()`: start playback; record `_start_wall_time = time.perf_counter()`; reset `_paused_duration = 0`.
- `pause()`: record `_pause_start = time.perf_counter()`.
- `resume()`: accumulate `_paused_duration += time.perf_counter() - _pause_start`.
- `stop()`.
- `current_ms() -> float`:
  ```
  elapsed = time.perf_counter() - _start_wall_time - _paused_duration
  return elapsed * 1000 + AUDIO_OFFSET_MS
  ```
  Uses the wall clock as the timing authority, excludes paused time, and applies `AUDIO_OFFSET_MS`.
- `is_playing() -> bool`.

**Timing contract:** Scoring always uses `audio.current_ms()` — never raw `time.perf_counter()`. `AUDIO_OFFSET_MS` is the manual A/V calibration knob: positive values shift the audio clock forward; negative values shift it backward. While paused, `current_ms()` must not advance.

**Supported formats:** MP3, OGG, WAV (pygame.mixer limitation).

**Verification:** Play a known-length file; assert `current_ms()` is within ±50 ms of wall clock after 5 seconds. Separately: pause for 2 seconds, resume, assert time did not advance during the pause (within ±5 ms).

---

### 9. `src/game/engine.py` — Game Engine

**Purpose:** Central state machine that drives the game loop.

**States:**
```
IDLE → COUNTDOWN → PLAYING → PAUSED → FINISHED
                 ↘
                  DEMO → FINISHED
```

**Collaborators are injected** through structural `Protocol`s — `Clock`
(satisfied by `AudioPlayer`, §8), `Scoring` (satisfied by `ScoringEngine`, §6),
and `DemoSource` (satisfied by `DemoPlayer`, §7). The engine never constructs
them; a setup/factory (introduced with §8) wires the real objects in. This keeps
the engine's single responsibility — driving state — uncoupled from audio
decoding, scoring math, and demo generation, and lets it be unit-tested against
fakes. (Implemented in Phase 2.4; design spec:
`ai-working-log/specs/2026-06-02-game-engine-design.md`.)

**`GameEngine(clock, scoring, *, countdown_ms=3000, end_padding_ms=2000)`**
- `load(chart, demo_source=None)`: bind the chart and optional demo source, call
  `scoring.reset(chart)` (clears score/combo and binds notes), reset to `IDLE`.
  A supplied `demo_source` selects a demo run.
- `start()`: `IDLE → COUNTDOWN`. The clock is **not** started yet; the countdown
  is timed by a `dt_ms` accumulator, so it works before the play clock runs.
- `update(dt_ms)`: per-frame.
  - `COUNTDOWN`: accumulate `dt_ms`; at `≥ countdown_ms`, `clock.play()` once and
    enter `PLAYING` (or `DEMO`).
  - `PLAYING`: `now = clock.current_ms()`; `scoring.tick(now)`; finish check.
  - `DEMO`: as `PLAYING`, plus forward each `demo_source.tick(now)` signal to
    `scoring.register_hit(sig.lane, sig.time_ms)` (signal's own time → perfect).
- `handle_input(lane)`: forward to `scoring.register_hit(lane, clock.current_ms())`
  **only** in `PLAYING`. The engine is the timestamp authority (raw pygame/rtmidi
  timestamps aren't in the audio-clock domain); no-op in `DEMO` and elsewhere.
- `pause()`/`resume()`: PLAYING/DEMO ↔ PAUSED via `clock.pause/resume`; redundant
  calls are no-ops; resume returns to the pre-pause play state.
- `current_ms() -> float`: scroll-position authority. Negative pre-roll in
  `IDLE`/`COUNTDOWN`; `clock.current_ms()` in PLAYING/DEMO/PAUSED; a cached
  finish time in `FINISHED` (so a position-resetting `clock.stop()` can't snap
  the scroll to 0).
- `countdown_value() -> int`: 3 → 2 → 1 for the HUD.
- `is_demo() -> bool`: True in DEMO, stable across a pause.
- `is_finished() -> bool`: `state == FINISHED`.

**Finish semantics:** the run ends at `chart.total_duration_ms + end_padding_ms`
(chart tail, after the last hit window closes plus a short ring-out) — **not** at
audio-file completion. `end_padding_ms` is the per-run knob for songs needing a
longer outro; no audio-duration contract is placed on `Clock` in v1.

**Verification:** Drive the state machine against fake clock/scoring/demo
collaborators — countdown threshold, scoring tick cadence, input stamping/gating,
demo forwarding, finish-at-tail with cached time, pause/resume. (See
`tests/test_game_engine.py`.)

---

### 10. `src/midi/device.py` — MIDI Device I/O

> **Implemented (Phase 4, Session 11).** See
> [`ai-working-log/specs/2026-06-07-midi-device-input-design.md`](specs/2026-06-07-midi-device-input-design.md).
> The implementation uses **frame polling** (`MidiInputDevice.poll()` drains
> `get_message()` each frame), not a background-thread callback queue — simpler
> and thread-safe; a callback upgrade for tighter timing is noted as future work.
> Adapter is `src/input/midi_input.py`; device selection + span calibration is
> `src/ui/midi_setup.py` (a MIDI port can't report its key count).

**Purpose:** Enumerate, open, and stream real-time MIDI messages from a physical MIDI keyboard.

**`MidiDeviceManager`**
- `list_devices() -> list[str]`: enumerate available MIDI input ports via `rtmidi`.
- `open(device_index: int)`: open port, register callback.
- `close()`.
- `on_message(callback: Callable[[int, int, int], None])`: callback receives `(note, velocity, timestamp_ms)`.
  - `velocity == 0` or `note_off` → treat as key release.

**Thread safety:** rtmidi delivers callbacks on a background thread; the callback pushes events onto a `queue.Queue`. The main thread drains this queue each frame.

**Verification:** Connect a MIDI keyboard (or use a virtual port), assert note events are received correctly.

---

### 11. `src/input/keyboard.py` — PC Keyboard Input

**Purpose:** Map PC keyboard key presses to lane indices.

**`KeyboardInputHandler`**
- `build_keymap(lane_count: int) -> dict[int, int]`: assigns pygame key codes to lanes.
  - Up to 8 lanes mapped to: `A S D F J K L ;` (indices 0–7).
  - More lanes split into two rows.
- `process_event(event) -> InputSignal | None`: returns `InputSignal(lane, time_ms)` on keydown.

**Verification:** Simulate pygame KEYDOWN events, assert correct lane signals returned.

---

### 12. `src/input/midi_input.py` — MIDI Input Adapter

**Purpose:** Translate MIDI device events to `InputSignal` objects using the chart's `KeyboardClass`.

**`MidiInputHandler`**
- `configure(kb_class: KeyboardClass)`: store MIDI low note.
- `process(note, velocity, time_ms) -> InputSignal | None`:
  - Ignore if `note < midi_low` or `note > midi_high`.
  - Ignore if `velocity == 0` (key release).
  - Return `InputSignal(lane = note - midi_low, time_ms)`.

**Verification:** Unit-test with mock note values, assert lane mapping is correct.

---

### 13. `src/ui/renderer.py` — In-Game Renderer (OpenGL + pygame overlay)

> **Implemented (Phase 3.3, Session 10).** See
> [`ai-working-log/specs/2026-06-07-opengl-renderer-design.md`](specs/2026-06-07-opengl-renderer-design.md).
> The HUD overlay is composited via a surface→GL-texture fullscreen quad
> (`src/ui/gl_overlay.py`), not `glDrawPixels`. The neon atlas is uploaded as a GL
> texture and sampled onto lane/note/hold/hit quads (`src/ui/gl_textures.py`,
> `src/ui/atlas.py`); placement math is the pure `src/ui/geometry.py`; the flat
> HUD/countdown/results layer is `src/ui/hud.py`.

**Purpose:** Draw all game visuals each frame using the OpenGL perspective scene (ported from `ui/graph/__init__.py`) with a pygame surface HUD overlay on top.

**Camera and perspective:**
- OpenGL window opened via `pygame.display.set_mode((W, H), DOUBLEBUF | OPENGL)`.
- `gluPerspective` + camera positioned above and behind the player, angled downward — produces the DJmax vanishing-point look where notes appear small far away and grow to full size at the hit bar.
- The board is a fixed-size quad in world space; notes travel along the Z axis toward the camera.

**Note position in world space:**
```
note_z = (note.time_ms - current_ms) * UNITS_PER_MS
```
Notes in the future have positive Z (far from camera); notes at hit time are at Z ≈ 0. The perspective projection maps this Z to the screen Y automatically — no manual perspective math needed.

**OpenGL draw pass (back to front):**
1. Clear color + depth buffer.
2. Board background (solid or gradient quad).
3. Lane dividers (semi-transparent vertical planes; black/white key tinting in MIDI mode).
4. Hit bar (horizontal quad with glow).
5. Falling note boxes (beveled 3D boxes with gradient shading; hold notes are elongated along Z).
6. Touch/hit effects (animated quad at the hit zone, fires on key press).

**pygame HUD overlay pass** (after `glFlush()`, before `pygame.display.flip()`):

Render all 2D text and overlay elements onto a `pygame.Surface(screen_size, SRCALPHA)`, blit to the display:

7. HUD: score, combo, accuracy (top-right).
8. Key labels (bottom of each lane, above bar).
9. Pause / countdown overlay when applicable.
10. **Demo mode badge** (top-left, semi-transparent) when `engine.is_demo()` is True.

The HUD path replaces `glDrawPixels` and keeps text/overlay rendering separate from the 3D draw pass.

**`Renderer`**
- `draw_frame(engine_state, notes, effects)`: called every frame.
- Resolution: default 1280×720; configurable.
- Target: 60 FPS via `pygame.Clock.tick(60)`.

---

### 14. `src/ui/menu.py` — Song Selection Screen

**Purpose:** Present available songs and allow the user to configure input mode.

**Flow:**
1. Scan `songs/` directory for subdirectories containing both `audio.*` and `chart.mid`.
2. For each song: display title, artist (from `meta.json` if present), key class, BPM.
3. **Check for MIDI devices** via `MidiDeviceManager.list_devices()`.
   - If **no MIDI devices found**: show the song list with input mode defaulting to `PC Keyboard`. A status line informs the user: *"No MIDI device detected — using PC Keyboard mode."* `MIDI Keyboard` option is greyed out.
   - If **devices are present**: all three input modes are available.
4. User selects a song and input mode (`PC Keyboard` / `MIDI Keyboard` / `Demo`).
5. If `MIDI Keyboard`: show device selection dropdown.
6. Confirm → `GameEngine.load()` → transition to gameplay (or `GameEngine.load(demo=True)` when Demo mode is selected).

---

### 15. `src/ui/results.py` — Results Screen

**Purpose:** Show post-song statistics.

**Displayed:**
- Song title and artist.
- Final score.
- Rank (S/A/B/C/D).
- Accuracy percentage.
- Per-judgment counts (PERFECT / GREAT / GOOD / MISS).
- Max combo.
- Option to retry or return to menu.
- **If demo mode**: the results screen still shows (a 100% / S-rank run every time), but adds a banner: *"Demo Mode — connect a MIDI device to play yourself."* The retry/menu prompt also offers *"Play this song"* which returns to the device-check flow.

---

### 16. `src/ui/effects.py` — Visual Effects

**Purpose:** Manage transient visual effects.

**Effects:**
- `HitEffect(lane, grade)`: color flash + expanding ring at hit position.
  - PERFECT: gold flash.
  - GREAT: blue flash.
  - GOOD: green flash.
  - MISS: red flash.
- `NoteTrail(lane)`: hold-note active glow while key is held.
- Effects are managed as a list; each has a TTL and is removed when expired.

---

## Data Flow Diagram

```
[MIDI File]
    |
    v
MidiParser ──────────────────────────────────────────┐
    |                                                  |
    v                                                  v
Classifier ──> KeyboardClass             [Audio File]
    |                                                  |
    v                                                  v
ChartBuilder ──> Chart                        AudioPlayer
    |                  \                           |
    v                   \──────────────────┐       |
GameEngine <──────────────────────────────>|<──────┘
    |  ^                                   |
    |  |                            ScoringEngine
    |  |                                   ^
    |  └───────── InputSignal ─────────────|
    |                   ^                  |
    |         ┌─────────┴──────────┐
    |    KeyboardInputHandler  MidiInputHandler
    |                                  ^
    |                             MidiDeviceManager
    v
Renderer ──> pygame display
```

---

## Input Mode Comparison

| Feature | PC Keyboard | MIDI Keyboard |
|---|---|---|
| Lane count | 4–8 (compressed) | Matches keyboard size (25–88) |
| Note mapping | Notes binned into N lanes | 1:1 note → lane |
| Key label | `A S D F J K L ;` | Note names (C3, D3, …) |
| Chord accuracy | No — same lane collapses | Yes — each key is distinct |
| Recommended for | Casual play | Authentic experience |

---

## Song Package Format

A song lives in its own subdirectory under `songs/`:

```
songs/my_song/
├── audio.mp3        # Required. Also accepts .ogg, .wav
├── chart.mid        # Required. Pattern source MIDI file
└── meta.json        # Optional metadata
```

**`meta.json` schema:**
```json
{
  "title": "My Song",
  "artist": "Artist Name",
  "bpm": 140,
  "preview_start_ms": 30000
}
```

If `meta.json` is absent, the song directory name is used as the title and BPM is read from the MIDI file.

---

## Configuration (`config.py`)

```python
SCREEN_WIDTH        = 1280
SCREEN_HEIGHT       = 720
TARGET_FPS          = 60
FALL_LEAD_MS        = 2000       # How far ahead notes appear
JUDGMENT_BAR_Y_PCT  = 0.88       # Bar position as fraction of screen height
HIT_WINDOWS = {
    "PERFECT": 35,
    "GREAT":   75,
    "GOOD":   120,
}
SONGS_DIR           = "songs"
AUDIO_BUFFER_MS     = 64         # pygame mixer buffer size
AUDIO_OFFSET_MS     = 0          # A/V sync calibration offset (ms); positive = shift audio forward
PC_KEY_MAP          = [K_a, K_s, K_d, K_f, K_j, K_k, K_l, K_SEMICOLON]
```

---

## Implementation Plan

### Phase 1 — MIDI Foundation

**Step 1.1 — Project scaffold**
- Create directory structure, `requirements.txt`, `config.py`, empty `__init__.py` files.
- `requirements.txt`: `pygame>=2.5`, `mido>=1.3`, `python-rtmidi>=1.5`, `PyOpenGL>=3.1.6`, `PyOpenGL_accelerate>=3.1.6`.
- Verify: `python -m pip install -r requirements.txt` succeeds on Win/Mac/Linux.

**Step 1.2 — MIDI Parser**
- Implement `MidiParser.parse()` in `src/midi/parser.py`.
- Handle tempo map changes mid-file.
- Verify: parse `songs/test/chart.mid` (a simple known MIDI), print note list, assert correct `time_ms` values.

**Step 1.3 — Keyboard Classifier**
- Implement `classify()` in `src/midi/classifier.py`.
- Verify: unit tests with note sets spanning each boundary (e.g., notes 48–72 → `25key`; notes 36–72 → `49key`).

**Step 1.4 — Chart Builder**
- Implement `ChartBuilder.build()` in `src/game/chart.py`.
- Verify: build chart in both `midi` and `pc` modes; assert lane indices ∈ `[0, lane_count)` for all notes.

---

### Phase 2 — Rendering Skeleton

**Step 2.1 — OpenGL window**
- `main.py`: open a 1280×720 window with `pygame.display.set_mode((W, H), DOUBLEBUF | OPENGL)`, set up perspective camera (`gluPerspective`), 60 FPS loop.
- Verify: window opens and closes cleanly on all platforms; GL context initialises without errors.

**Step 2.2 — Lane renderer**
- Port the board, lane dividers, and hit bar GL draw code from `ui/graph/__init__.py` into `src/ui/renderer.py`. Wire to `LaneLayout` for lane count and geometry.
- Verify: lanes render correctly for 8-lane and 25-lane configurations; perspective taper is visible; bar is at the correct screen position.

**Step 2.3 — Falling notes**
- Add note Z-position update to `GameEngine.update()`: `note_z = (note.time_ms - current_ms) * UNITS_PER_MS`.
- Renderer draws each note as a beveled 3D box at its Z position; hold notes elongated along Z.
- Verify: spawn a note at t=0 with fall lead 2000 ms; it should arrive at the hit bar at exactly 2000 ms wall time.

**Step 2.4 — Audio player**
- Implement `AudioPlayer` in `src/audio/player.py`.
- Integrate into `GameEngine`: start audio on game start.
- Verify: play a 10-second track; `current_ms()` matches wall clock within ±50 ms.

---

### Phase 3 — Input and Scoring

**Step 3.1 — PC keyboard input**
- Implement `KeyboardInputHandler`.
- Wire into game loop: keydown → `InputSignal` → `GameEngine.handle_input()`.
- Verify: press mapped keys during gameplay; `InputSignal` logged with correct lane and timestamp.

**Step 3.2 — Scoring engine**
- Implement `ScoringEngine` with all hit windows.
- Wire into `GameEngine`.
- Verify: unit tests for each judgment; miss detection for notes that expire.

**Step 3.3 — MIDI device input**
- Implement `MidiDeviceManager` and `MidiInputHandler`.
- Wire into game loop alongside keyboard input.
- Verify: connect MIDI keyboard; press keys; assert correct lane signals and no duplicate events.

---

### Phase 4 — Full Game Loop

**Step 4.1 — Song selection menu**
- Implement `src/ui/menu.py`.
- Scan `songs/` directory; display list; handle selection and mode choice.
- Verify: add two test songs; navigate menu; confirm correct song+mode loads.

**Step 4.2 — Countdown and game start transition**
- Add `COUNTDOWN` state to `GameEngine`; display 3–2–1 overlay in renderer.
- Verify: countdown animates; audio starts after count reaches 0.

**Step 4.3 — Results screen**
- Implement `src/ui/results.py`.
- Transition from `FINISHED` state.
- Verify: all stats match `ScoringEngine` values; retry and menu navigation work.

**Step 4.4 — Demo mode**
- Implement `src/game/demo.py` (`DemoPlayer`).
- Menu detects MIDI devices, defaults to PC Keyboard when none are available, greys out MIDI Keyboard, and keeps Demo as an explicit selectable mode.
- `GameEngine.update()` routes demo signals through scoring and hit effects.
- Renderer/results screens display demo state with a "DEMO" badge, demo banner, and "Play this song" option.
- Verify: launch with no MIDI device connected; song list shows with PC Keyboard default; select Demo mode manually; score reaches 1,000,000 / 100% / S rank; "DEMO" badge is visible throughout.

---

### Phase 5 — Polish

**Step 5.1 — Hit effects**
- Implement `effects.py` particle effects.
- Add key-press column flash.
- Verify: each judgment grade produces the correct color.

**Step 5.2 — HUD**
- Score, combo, and accuracy update in real time.
- Combo pop animation on increment.
- Verify: score matches `ScoringEngine.score` each frame.

**Step 5.3 — Large keyboard viewport** (49key+)
- Implement scrolling viewport: fixed window of ~25 visible lanes, auto-centered on the most recently active lane cluster (last ~1 second of input).
- Add miniature keyboard strip to HUD showing all lanes with the visible window highlighted.
- Verify: a 49-key chart renders with lane width ≥ 14 px; viewport follows active lanes; miniature strip shows full range.

**Step 5.4 — Cross-platform verification**
- Run full playthrough on Windows, macOS, and Ubuntu.
- Verify: no import errors, MIDI device enumeration works, audio sync is consistent.

**Step 5.5 — Packaging**
- Add `build.sh` / `build.bat` using PyInstaller.
- Bundle `assets/` and a sample `songs/` directory.
- Verify: resulting binary runs without Python installed.

---

## Verification Matrix

| Module | Test type | Pass criterion |
|---|---|---|
| MidiParser | Unit | Known MIDI → correct NoteEvent times (±1 ms) |
| Classifier | Unit | All 6 boundary conditions correct |
| ChartBuilder | Unit | All lanes in valid range for both modes |
| ScoringEngine | Unit | All 4 judgment types, combo reset, score formula |
| AudioPlayer | Integration | `current_ms()` within 50 ms of wall clock |
| GameEngine | Integration | Note reaches bar_y at expected audio time |
| KeyboardInputHandler | Integration | Keypress maps to correct lane |
| MidiInputHandler | Integration | MIDI note maps to correct lane |
| DemoPlayer | Unit | All notes hit; `ScoringEngine.accuracy == 1.0` at end |
| Demo mode (no device) | End-to-end | Song list shown with PC Keyboard default; Demo selectable; DEMO badge visible; 100% score |
| Renderer | Visual | 60 FPS on reference hardware, no flicker |
| Full game | End-to-end | Song loads, plays, scores, results show correctly |

---

## Out of Scope (v1)

- Online leaderboards.
- Custom skin / theme system.
- Multiplayer.
- Note editor / authoring tool.
- Video backgrounds.
- Auto-sync offset calibration (manual offset in config is sufficient for v1).
