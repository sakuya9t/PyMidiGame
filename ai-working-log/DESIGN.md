# MidiMania — Design Document

## Overview

MidiMania is a cross-platform, DJmax-style rhythm game where note patterns fall from the top of the screen and players press the corresponding key as each note reaches the judgment bar. Patterns are auto-generated from MIDI files, and the game supports both PC keyboard and physical MIDI keyboard input.

If no MIDI device is detected at startup, the game enters **Demo Mode**: the selected song plays automatically with all notes hit at perfect timing, showing a live 100% score run. Demo mode lets first-time users see the game in action and verify audio/visual output without needing hardware connected.

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
- Handle `type 0` (single track), `type 1` (multi-track sync), and `type 2` (multi-track async) MIDI files.
- Walk through all tracks, accumulate absolute ticks per track, then apply the tempo map (from `set_tempo` meta messages) to convert ticks → milliseconds.
- Ignore `note_off` for duration calculation: match each `note_on` (velocity > 0) with the next `note_off` or `note_on` with velocity 0 on the same channel+note.
- Strip notes with velocity 0 at parse time.

**Verification:** Unit test with a known MIDI file; assert note times match expected values (e.g., a 120 BPM MIDI with a note at beat 1 = 500 ms).

---

### 2. `src/midi/classifier.py` — Keyboard Size Classifier

**Purpose:** Determine the minimum standard keyboard size that covers all notes in a chart, and produce the canonical lane-to-note mapping.

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
- If no class covers the range, return `88key` as a fallback.

**`KeyboardClass` dataclass:**

```python
@dataclass
class KeyboardClass:
    name: str          # "25key", "49key", etc.
    key_count: int
    midi_low: int      # Lowest MIDI note in this class
    midi_high: int     # Highest MIDI note in this class
    lane_count: int    # == key_count (MIDI mode) or compressed (PC mode)
```

**Lane assignment (MIDI keyboard mode):**
```
lane = note - midi_low   # 0-indexed, left to right
```

**Verification:** Unit tests with crafted note sets, assert correct class is returned and lane indices are within range.

---

### 3. `src/game/note.py` — Note Data Class

**Purpose:** Represents a single falling note in the game world.

```python
@dataclass
class Note:
    lane: int              # Lane index (0-based)
    midi_note: int         # Underlying MIDI note number
    time_ms: float         # When it should be hit (audio time)
    duration_ms: float     # Hold duration (0 for tap notes)
    y: float               # Current screen Y position (pixels)
    hit: bool = False      # Has been hit
    missed: bool = False   # Passed the bar without a hit
```

---

### 4. `src/game/chart.py` — Chart Builder

**Purpose:** Convert a `list[NoteEvent]` + `KeyboardClass` into a sorted `list[Note]` ready for the game engine.

**`ChartBuilder.build(events, kb_class, mode) -> Chart`**

- `mode`: `"midi"` (1:1 note→lane) or `"pc"` (compressed lanes).
- In `"midi"` mode: `lane = event.note - kb_class.midi_low`.
- In `"pc"` mode: quantize the note pitch range into N lanes (default 8) using equal-width bins.
- Notes are sorted ascending by `time_ms`.
- Simultaneous notes (chords within ±5 ms) are grouped as a `Chord`.

**`Chart` dataclass:**
```python
@dataclass
class Chart:
    notes: list[Note]
    kb_class: KeyboardClass
    mode: str
    total_duration_ms: float
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
- Max lanes displayed: limited by screen width; each lane minimum 30 px wide.
- For large keyboards (49+), lanes are drawn smaller; a horizontal scroll indicator shows visible range.
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
- Returns the list of signals generated this tick; the caller (`GameEngine`) feeds them directly to `ScoringEngine.register_hit()` and also triggers the hit visual effect so the screen looks fully animated.

**Why tick-driven rather than pre-scheduled:**
Generating signals inside the game loop keeps demo behaviour consistent with how real input is processed. If the game is paused and resumed, the pending queue simply resumes from where it left off.

**Active visual feedback:**
The renderer must treat demo signals identically to real player input — column flash, PERFECT judgment text, score increment. The player watching demo mode sees the full game in action.

**Verification:** Load a 10-note chart; run `DemoPlayer.tick()` advancing time step by step; assert all 10 signals are generated and `ScoringEngine.score == 1_000_000` at end with `accuracy == 1.0`.

---

### 8. `src/audio/player.py` — Audio Player

**Purpose:** Load and play an audio file, provide a reliable current-time query.

**`AudioPlayer`**
- `load(path: str)`: load file into `pygame.mixer`.
- `play()`: start playback; record `start_wall_time = time.perf_counter()`.
- `pause() / resume()`.
- `stop()`.
- `current_ms() -> float`: `(time.perf_counter() - start_wall_time) * 1000`. This avoids pygame's imprecise `get_pos()`.
- `is_playing() -> bool`.

**Supported formats:** MP3, OGG, WAV (pygame.mixer limitation).

**Verification:** Play a known-length file, assert `current_ms()` is within ±50 ms of wall clock after 5 seconds.

---

### 9. `src/game/engine.py` — Game Engine

**Purpose:** Central state machine that drives the game loop.

**States:**
```
IDLE → COUNTDOWN → PLAYING → PAUSED → FINISHED
                 ↘
                  DEMO → FINISHED
```

**`GameEngine`**
- `load(chart, audio_path, demo: bool = False)`: prepare chart and audio player. If `demo=True`, also instantiate a `DemoPlayer`.
- `start()`: begin countdown (3–2–1), then `play()` audio and enter `PLAYING` or `DEMO`.
- `update(dt_ms)`: called every frame.
  - In `PLAYING` or `DEMO`: advance note Y positions, call `scoring.tick(audio.current_ms())`, collect expired notes.
  - In `DEMO` additionally: call `demo_player.tick(audio.current_ms())` and forward each returned signal to `scoring.register_hit()` and the hit-effect system.
  - Note Y formula: `y = spawn_y + (current_ms - note.time_ms + fall_lead_ms) * pixels_per_ms`
    - `fall_lead_ms`: how many ms before the beat a note should appear at the top (e.g., 2000 ms).
    - `pixels_per_ms = (bar_y - spawn_y) / fall_lead_ms`
- `handle_input(lane, time_ms)`: forward to `ScoringEngine.register_hit`. No-op in `DEMO` state (real input is ignored).
- `is_demo() -> bool`: returns True when in DEMO state.
- `is_finished() -> bool`: all notes resolved and audio done.

**HUD in demo mode:** Display a "DEMO" badge in the top-left corner of the screen so it is always clear the game is playing itself. The score, combo, and judgment displays behave identically to normal play.

**Verification:** Simulate a two-note chart at fixed timestamps, assert notes reach `bar_y` at correct wall time. Separately, run in demo mode and assert `scoring.accuracy == 1.0` at end.

---

### 10. `src/midi/device.py` — MIDI Device I/O

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

This approach replaces `glDrawPixels` (which copied raw pixel data from CPU to GPU every frame) with pygame surface blitting, which is both faster and simpler to maintain.

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
   - If **no MIDI devices found**: automatically start demo mode on the first available song. Skip manual song selection entirely; the game enters `DEMO` state immediately. A status message informs the user: *"No MIDI device detected — playing in Demo Mode. Connect a device and restart to play."*
   - If **devices are present**: continue to the normal selection flow.
4. User selects a song and input mode (`PC Keyboard` / `MIDI Keyboard`).
5. If `MIDI Keyboard`: show device selection dropdown.
6. Confirm → `GameEngine.load()` → transition to gameplay (or `GameEngine.load(demo=True)` in demo mode).

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
- In `src/ui/menu.py`: call `MidiDeviceManager.list_devices()` on startup; if empty, call `GameEngine.load(demo=True)` on the first available song.
- In `GameEngine.update()`: when `is_demo()`, call `demo_player.tick()` and route signals to scoring and hit effects.
- In `Renderer`: draw "DEMO" badge when `engine.is_demo()`.
- In `src/ui/results.py`: show demo banner and "Play this song" option when demo mode.
- Verify: launch with no MIDI device connected; game auto-starts demo; score reaches 1,000,000 / 100% / S rank; "DEMO" badge is visible throughout.

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

**Step 5.3 — Large keyboard scrolling** (49key+)
- For MIDI mode with many lanes, add left/right scroll to show active note region.
- Or: auto-center view on the most recently active lane cluster.
- Verify: a 49-key chart renders without lanes being too narrow to see.

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
| Demo mode (no device) | End-to-end | Auto-starts demo on launch; DEMO badge visible; 100% score |
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
