# PyMidiGame — Development Analysis Report

## Project Goal (Recap)

A DJmax-style rhythm game where:
- Patterns fall top-to-bottom; the player presses a key when a pattern reaches the hit bar
- Controlled by a MIDI keyboard (MIDI signals → game input)
- Patterns are auto-generated from an input MIDI file in the game directory
- A paired audio file plays the music during gameplay
- The MIDI file is classified by keyboard size (25/32/37/49/61/88 key), and the physical keyboard used must match
- Must run cross-platform: Windows, macOS, major Linux distributions
- **Demo mode**: when no MIDI device is plugged in at startup, the game automatically plays itself — audio plays, all notes are hit with perfect timing, and the score runs to 100%. The player can watch the song and verify everything works without needing hardware connected. A "DEMO" badge is displayed throughout and the results screen prompts the user to connect a device to play for real.

---

## What the Repo Got Right

### 1. MIDI Input Pipeline Is Well-Structured

The MIDI input stack is legitimately good:

- **`InputMidiQueue`** runs on its own thread and continuously polls the MIDI device using `pygame.midi`. It converts raw MIDI bytes into structured events (`{'id': 'C3', 'event': 'EVENT_KEY_DOWN'}`).
- **`midis2events.py`** correctly decodes all major MIDI status codes (NOTE_ON, NOTE_OFF, key aftertouch, controller change, pitch bend) and distinguishes NOTE_OFF from NOTE_ON with velocity 0 (a real-world quirk that many implementations miss).
- **`KeyMapper.py`** correctly derives note names from MIDI key numbers using the standard formula (`rank = note % 12`, `octave = note // 12 - 1`), including black key detection.

This is a solid foundation for MIDI keyboard input.

### 2. MIDI File Parsing Is Correct

`midi/__init__.py` uses `mido` and correctly:
- Reads `set_tempo` messages to derive BPM
- Reads time signature (`numerator`, `denominator`)
- Converts MIDI ticks to beats using the standard formula: `beats = ticks / PPQ`
- Constructs a `Note` list with `start`, `duration`, and `note_name`, which is exactly what a rhythm game needs to drive pattern rendering

### 3. Threading Architecture Is Reasonable

The use of separate threads for MIDI input, UI events, and keyboard events is the right approach to prevent frame drops. The `Logger` also runs on its own thread to avoid blocking the render loop. The `Store` object as a centralized shared state is a sensible pattern.

### 4. 3D OpenGL Rendering Has Real Ambition

The 3D rendering code in `ui/graph/__init__.py` shows genuine effort:
- A perspective projection with a rotated camera gives a DJmax-like vanishing-point look
- Notes are rendered as 3D beveled boxes with gradient shading
- A "touch effect" (animated gradient at the hit zone) fires on key press
- Track dividers and the hit bar are rendered as semi-transparent geometry
- Notes are clipped to the game board boundaries

### 5. Configuration System Is Usable

`Config.py` provides a clean path-based accessor (`config.get("midi-device/device-id")`), persists to JSON, and the UI for mapping MIDI notes to game keys is fully functional and saves correctly.

### 6. MIDI Device Management

`InputController.py` handles device listing, selection via dropdown, switching mid-session, and error recovery gracefully. This is non-trivial and it works.

---

## What the Repo Got Wrong

### Critical Problems

#### 1. `requirements.txt` Is Incomplete and Outdated

The file lists only `pygame==1.9.6` and generic Python tooling. The following packages are actively imported in the codebase but **missing entirely**:

| Package | Used In |
|---|---|
| `pygame-gui` | ConfigBox.py, UI system |
| `mido` | midi/__init__.py |
| `python-rtmidi` | MIDI backend for mido |
| `PyOpenGL` | ui/graph/__init__.py |
| `pyautogui` | InputMidiQueue.py |

Any fresh clone is broken immediately. `pygame==1.9.6` is also dangerously old (2019); the current version is 2.x with substantial API changes.

#### 2. Audio Is Not Integrated — At All

`Mp3Player/` exists and wraps Windows MCI (Media Control Interface) via `ctypes.windll.winmm`. `MusicPlayer.py` is a standalone test script with a hardcoded file path. **There is no code anywhere that:**
- Starts audio playback when the game starts
- Syncs audio time to game scroll offset
- Pauses or stops audio when the game state changes

The game is silent during play. This is the single biggest functional gap.

#### 3. `Mp3Player` Is Windows-Only and Non-Portable

Using `ctypes.windll.winmm` hard-codes Windows. It will raise an `AttributeError` immediately on macOS or Linux. The cross-platform goal is impossible with this module.

#### 4. No Hit Detection or Game Mechanics

The game renders falling notes and accepts MIDI input, but **the two systems never talk to each other**. There is no code that:
- Compares the current time position to note positions
- Registers a hit or miss when a key is pressed
- Tracks score, combo, or accuracy
- Ends the game when the song finishes

It is a MIDI visualizer, not a game.

#### 5. No Demo Mode

There is no fallback for when no MIDI device is connected. The current startup flow unconditionally tries to open device ID 5 from config; if it fails, the game silently starts with no input and no indication of what to do. A first-time user with no device plugged in sees a black screen with falling notes they cannot interact with, no score, and no guidance.

#### 6. MIDI Keyboard Size Classification Is Missing

The original goal requires detecting how many keys a MIDI file actually uses (to classify as 25/32/37/49/61/88 key) and warning/erroring if the player's physical keyboard doesn't cover the required range. This feature does not exist anywhere in the codebase.

#### 7. The MIDI Input Mode Is Architecturally Wrong for the Game Goal

The current design uses `pyautogui.keyDown()` / `keyUp()` to simulate **keyboard presses** from MIDI input. This is a workaround for mapping a MIDI keyboard to a game that responds to keyboard keys — but for a game that is *designed* for MIDI input from the start, this is backwards. The game itself should consume MIDI events directly and compare them against note data. The `pyautogui` indirection adds latency, requires OS-level permissions on macOS/Linux, and adds unnecessary complexity.

#### 8. Song Selection Does Not Exist

There is no song selection screen. MIDI files are hardcoded references. The user cannot browse and pick a song + audio pair from the game directory. This is a fundamental missing feature.

#### 9. The 2D Scene Is "Deprecated" but Never Removed

`GameStageScene.py` is marked deprecated and the code has a comment saying the 3D scene replaced it, yet it still exists and is still referenced in some places. This creates confusion about which rendering path is canonical.

#### 10. Thread Safety Is Not Enforced

Multiple threads (`InputMidiQueue`, `InputUIEventQueue`, `InputKeyboardEventQueue`) read and write to the `Store` object concurrently with no locks, mutexes, or thread-safe data structures. On CPython the GIL provides partial protection, but this is not safe by design and will cause subtle bugs on PyPy or future Python versions.

#### 11. `pygame.midi` Is Used Instead of `python-rtmidi`

`pygame.midi` is known to have poor device detection, high latency (~10–20ms extra), and unreliable behavior on some platforms. `python-rtmidi` (or `mido` with an `rtmidi` backend) is the standard for low-latency MIDI I/O and is already listed as a dependency — but `pygame.midi` is what's actually used everywhere.

### Minor Problems

- **`swtich_input()`** is a typo for `switch_input()` in `InputMidiQueue.py`
- **The OpenGL renderer uses `glBegin`/`glEnd` (immediate mode)**, which is deprecated in OpenGL 3.x and unavailable in OpenGL ES / WebGL. For a modern engine, VBOs and shaders would be more appropriate, but this is a minor concern for a desktop Python game.
- **`glDrawPixels` for text rendering** is extremely slow — it copies pixel data from the CPU to GPU every frame. A proper texture cache for font glyphs would be much faster.
- **No error handling for malformed MIDI files** — a corrupt or non-standard MIDI file will crash the parser with an unhandled exception.
- **No FPS cap or delta-time gameplay** — the game loop runs at whatever the frame rate happens to be, which means game speed will vary on different machines.
- **`config.json` stores the MIDI device by numeric ID**, which changes if the user reconnects devices in a different order. Device name would be more stable.

---

## Required Changes to Reach the Original Goal

The following is an ordered list of what must be built or rebuilt.

---

### Phase 1 — Foundation Cleanup (Do First)

#### 1.1 Fix Dependencies
Replace `requirements.txt` with the packages the new architecture actually requires:
```
pygame>=2.5.0
mido>=1.3.0
python-rtmidi>=1.5.0
PyOpenGL>=3.1.6
PyOpenGL_accelerate>=3.1.6
```
Remove `pyautogui` entirely — it will not be needed after the architecture fix below. `pygame-gui` is also not needed: all UI (menus, HUD, results) is rendered with pygame surfaces or as overlays on the GL frame. `PyOpenGL` is retained: the in-game scene uses OpenGL for its perspective 3D renderer (see §1.5).

#### 1.2 Remove `pygame.midi`, Use `mido` + `rtmidi` Throughout
Replace all `pygame.midi` usage in `InputMidiQueue.py` and `MidiDeviceSettings.py` with `mido.open_input()` using the `rtmidi` backend. This gives lower latency, reliable cross-platform behavior, and a cleaner API.

#### 1.3 Remove `pyautogui` Keyboard Simulation
The game should consume MIDI events directly, not simulate keyboard presses. Remove the `pyautogui.keyDown()`/`keyUp()` calls. Instead, MIDI note events should be pushed onto a thread-safe queue and consumed by the game loop directly for hit detection.

#### 1.4 Replace `Mp3Player` with `pygame.mixer`
`pygame.mixer` supports MP3 (via SDL_mixer), OGG, and WAV on all platforms. Use `pygame.mixer.music.load()` and `pygame.mixer.music.play()`. This is already a dependency and works on Windows, macOS, and Linux. Remove the entire `Mp3Player/` directory.

#### 1.5 Refactor OpenGL Renderer — Delete Only the Deprecated 2D Scene
Delete `ui/scenes/GameStageScene.py` and all references to it. **Keep `ui/graph/__init__.py`** — the OpenGL 3D renderer is the canonical in-game renderer. It already delivers the core visual requirement: notes appear small at the vanishing point (far away) and grow to full size at the hit bar, giving the DJmax-style perspective look.

**Refactoring work required:**
- Decouple from `Store`/`SceneController`; wire to the new `GameEngine`, `Chart`, and `ScoringEngine` instead
- Fix `glDrawPixels` text rendering (CPU→GPU pixel copy every frame, extremely slow): replace with **pygame surface blit on top of the GL frame**. After GL draw calls, render HUD text, DEMO badge, and overlays onto a `pygame.Surface` with `SRCALPHA`, blit it to the display, then call `pygame.display.flip()`. This is fast and requires no GL font textures.
- Move into `src/ui/renderer.py` in the new directory layout

**What does NOT change:** the perspective projection, camera setup, beveled note boxes, board geometry, and hit zone effects. These are already correct and do not need to be rewritten.

Target resolution: **1280×720**. Target frame rate: **60 FPS** via `pygame.Clock.tick(60)`.

#### 1.6 Thread Safety
Wrap `Store` object mutations in a `threading.Lock`. Any property that is written by an input thread and read by the render thread must be access-controlled.

---

### Phase 2 — Game Architecture (Core Features)

#### 2.1 Audio + MIDI Sync System
This is the most important architectural piece. The game must have a **master clock** based on wall time, not on pygame's internal audio position counter:

```
Master Clock
├── AudioPlayer.current_ms() = (time.perf_counter() - start_wall_time) * 1000
│   (NOT pygame.mixer.music.get_pos() — that can drift or reset on buffer underruns)
├── Note Y position = spawn_y + (current_ms - note.time_ms + FALL_LEAD_MS) * pixels_per_ms
│   where pixels_per_ms = (bar_y - spawn_y) / FALL_LEAD_MS
│         FALL_LEAD_MS = 2000 ms (how far ahead of the beat a note appears at spawn)
└── All note positions and hit windows computed in milliseconds from this single clock
```

On pause, `perf_counter` accumulation is suspended; on resume it continues from where it left off. All note timing is stored in absolute milliseconds (`note.time_ms`), not beats — this keeps the note position formula a simple linear function of the clock.

#### 2.2 Hit Detection
On each NOTE_ON input event, find the nearest unresolved note in the same lane and classify against millisecond windows (measured from `note.time_ms`):

| Grade | Window |
|---|---|
| PERFECT | ±35 ms |
| GREAT | ±75 ms |
| GOOD | ±120 ms |
| MISS | outside window or key not pressed |

Score formula (per note):
```
base_score = 1_000_000 / total_notes
PERFECT → base_score × 1.0
GREAT   → base_score × 0.7
GOOD    → base_score × 0.4
MISS    → 0, reset combo
```

Mark hit notes so they stop rendering. Accumulate score, combo, and max combo.

On each NOTE_OFF event (for hold notes): register hold release accuracy at `note.time_ms + note.duration_ms`.

#### 2.3 Miss Detection
On each frame (`ScoringEngine.tick(current_ms)`), any note whose `time_ms` is more than 120 ms in the past (i.e., the GOOD window has fully elapsed) without having been hit should be marked as MISS, removed from the active note list, and the combo reset.

#### 2.4 Score and Combo Display
Render current score, combo count, and accuracy percentage as HUD text overlaid on the OpenGL game scene. Use the pygame surface blit approach introduced in §1.5: after each GL draw pass, blit a `pygame.Surface` (SRCALPHA) carrying all text elements — score, combo pop animation, accuracy, key labels, DEMO badge — onto the display before `pygame.display.flip()`. This replaces the existing `glDrawPixels` approach with something that is both fast and easy to extend.

#### 2.5 Demo Mode (No Device Fallback)

On startup, call `MidiDeviceManager.list_devices()`. If the list is empty:
- Skip song selection; auto-load the first available song from the `songs/` directory.
- Call `GameEngine.load(chart, audio_path, demo=True)`.
- Display a persistent **"DEMO" badge** (top-left, semi-transparent) throughout gameplay.
- Show a status message: *"No MIDI device detected — playing in Demo Mode. Connect a device and restart to play."*
- After the song finishes, show the results screen (always 100% / S rank in demo) with a banner and *"Play this song"* option.

**`DemoPlayer` implementation:**
```
class DemoPlayer:
    def __init__(self, chart, scoring): ...
    def tick(self, current_ms) -> list[InputSignal]: ...
```
- On construction, builds a pending queue of all chart notes sorted by `time_ms`.
- Each call to `tick(current_ms)` pops every note whose `time_ms <= current_ms` and returns an `InputSignal(lane=note.lane, time_ms=note.time_ms)`. Hitting at exactly the target time is always within the PERFECT ±35 ms window.
- For hold notes (duration > 0): a matching release signal is returned at `note.time_ms + note.duration_ms`.
- `GameEngine.handle_input()` is a **no-op** in `DEMO` state — real player input is ignored.
- The renderer treats demo signals identically to real player input (column flash, PERFECT text, score increment). No special cases in `ScoringEngine` are required; demo mode only differs in the input source.

#### 2.6 Keyboard Size Classification
When loading a MIDI file, scan all note events and determine the minimum and maximum MIDI note numbers used. Map this range to the standard keyboard sizes:

| Keys | MIDI Range |
|---|---|
| 25 key | C3–C5 (MIDI 48–72) |
| 32 key | F2–C5 (MIDI 41–72) |
| 37 key | F2–F5 (MIDI 41–77) |
| 49 key | C2–C6 (MIDI 36–84) |
| 61 key | C2–C7 (MIDI 36–96) |
| 88 key | A0–C8 (MIDI 21–108) |

Select the smallest standard size that covers the song's range. Display this requirement on the song selection screen and warn the player if their detected MIDI device's key range is smaller.

#### 2.7 MIDI Device Key Range Detection
Query the connected MIDI device name and attempt to infer its key count from the device name string (most devices include "25", "49", "61", etc. in their name). Provide a manual override setting in the config.

---

### Phase 3 — Game Flow (Missing Screens)

#### 3.1 Song Selection Screen
Build a song browser that:
- Scans `songs/` for **subdirectories**, each containing `audio.mp3` (or `.ogg`/`.wav`), `chart.mid`, and an optional `meta.json`
- `meta.json` carries `{ "title", "artist", "bpm", "preview_start_ms" }`; if absent, the directory name is the title and BPM comes from the MIDI file
- Displays song title, artist, BPM, duration, and required keyboard size class
- Lets the player select with arrow keys and confirm

After song selection, the player chooses **input mode**:
- **PC Keyboard** — note range is compressed into 4–8 lanes; key bindings are `A S D F J K L ;`
- **MIDI Keyboard** — 1:1 note → lane mapping; requires a connected device

If `MidiDeviceManager.list_devices()` returns an empty list, skip song selection entirely and auto-load the first available song in demo mode (see §2.5).

#### 3.2 Game States
Implement a proper state machine:
```
IDLE → SONG_SELECT → COUNTDOWN → PLAYING → PAUSED → FINISHED → SONG_SELECT
                              ↘
                               DEMO → FINISHED
```

Key states:
- `COUNTDOWN`: 3–2–1 overlay before audio starts
- `PLAYING`: normal player input is active; `handle_input(lane, time_ms)` routes to `ScoringEngine`
- `DEMO`: `DemoPlayer.tick()` generates hits automatically; `handle_input` is a no-op
- `FINISHED`: all notes resolved and audio done; transition to results screen

Currently the game launches directly into the scene with no state management.

#### 3.3 Results Screen
After the song ends, show:
- Score breakdown (PERFECT / GREAT / GOOD / MISS counts)
- Accuracy percentage (PERFECT + GREAT counts / total notes)
- Max combo
- Letter grade with thresholds: **S** ≥ 98% · **A** ≥ 90% · **B** ≥ 75% · **C** ≥ 60% · **D** < 60%
- Song title and artist

#### 3.4 Pause and Resume
SPACE (or a dedicated MIDI note) should pause both audio and the game clock simultaneously. Resuming should restart both from the same position.

---

### Phase 4 — Polish and Correctness

#### 4.1 Note Lane Assignment
Currently notes are mapped to lanes by their position in the 32-key window. For the new architecture, lanes should be determined by the note's position relative to the MIDI file's key range, not hardcoded to 32 keys. The visible lane count should equal the keyboard size classification (e.g., 25 lanes for a 25-key song).

#### 4.2 Delta-Time Based Gameplay
The scroll speed and all time-based computations must use the audio clock (in milliseconds), not frame count. This ensures correct behavior regardless of frame rate.

#### 4.3 Long Note (Hold) Support
Many MIDI files contain long notes (notes with duration > 0). The renderer already supports drawing these as elongated boxes, but hit detection must handle:
- Key-down at note head → start hold
- Key-up before note tail → early release penalty
- Key-up at note tail → full score

#### 4.4 MIDI File + Audio File Validation
On song load, validate:
- MIDI file parses without error
- Audio file exists with the same base name
- Audio file format is supported
- MIDI file contains at least one note
- Song duration is reasonable (> 5 seconds)

Provide friendly error messages instead of crashes.

#### 4.5 Config Migration
Change `config.json` to store MIDI device by name instead of numeric ID. Add a config schema version number so future changes can migrate old configs gracefully. Define all game-wide constants in a dedicated `config.py` module (not scattered in source files):
```python
SCREEN_WIDTH       = 1280
SCREEN_HEIGHT      = 720
TARGET_FPS         = 60
FALL_LEAD_MS       = 2000      # ms ahead of target time that a note spawns at the top
JUDGMENT_BAR_Y_PCT = 0.88      # bar position as fraction of screen height
HIT_WINDOWS        = {"PERFECT": 35, "GREAT": 75, "GOOD": 120}  # ms
AUDIO_BUFFER_MS    = 64
PC_KEY_MAP         = [K_a, K_s, K_d, K_f, K_j, K_k, K_l, K_SEMICOLON]
```

#### 4.6 PC Keyboard Input Mode
Implement `KeyboardInputHandler` for players using a standard keyboard instead of a MIDI device:
- Default bindings: `A S D F J K L ;` map to lanes 0–7
- `process_event(pygame_event) → InputSignal | None`: returns a signal on KEYDOWN; None otherwise
- For charts with more than 8 lanes, add a second keyboard row or require MIDI mode
- Display bound key labels at the bottom of each lane column
- `NOTE_OFF` equivalent: KEYUP events do not score but are needed to release hold notes

#### 4.7 Visual Effects System
Implement `src/ui/effects.py` to manage transient visual feedback:
- `HitEffect(lane, grade)`: color-coded flash + expanding ring at the judgment bar position
  - PERFECT: gold · GREAT: blue · GOOD: green · MISS: red
- `NoteTrail(lane)`: glow overlay on a hold-note column while the key is held
- Each effect has a TTL (time-to-live in ms); the effects list is filtered each frame to remove expired entries
- The renderer treats demo-mode signals identically to real player input — every PERFECT hit in demo mode triggers the gold flash and score increment, so the game looks fully animated during auto-play

#### 4.8 Large Keyboard Scrolling (49+ Key)
For songs classified as 49key, 61key, or 88key the number of lanes exceeds what fits comfortably at readable width on a 1280 px screen. Implement one of:
- **Auto-center**: viewport follows the cluster of most recently active lanes
- **Scroll indicator**: a thin horizontal bar at the bottom shows the full-width keyboard and the current visible slice

Minimum lane width is 30 px. At minimum width a 49-key song fits; 61key and 88key require scrolling.

#### 4.9 Chord Grouping
`ChartBuilder` must group notes that fall within ±5 ms of each other as a simultaneous chord. Hit detection for a chord should require all chord notes to be pressed within the window; missing any chord note counts as a MISS for that note individually. The renderer draws chords with the same Y position for all constituent notes.

#### 4.10 MIDI NOTE_OFF Handling in Input Adapter
`MidiInputHandler` must treat `velocity == 0` on a `note_on` message as a `note_off` (this is standard MIDI running-status behaviour that many MIDI controllers use instead of sending a true `note_off` message). Only `note_on` with `velocity > 0` generates an `InputSignal` for hit detection.

---

### Phase 5 — Packaging and Distribution

#### 5.1 PyInstaller Build
Bundle the application and all assets into a single standalone executable per platform using PyInstaller:
- `build.bat` for Windows, `build.sh` for macOS and Linux
- Bundle `assets/` (fonts, SFX) and a sample `songs/` directory so the binary is self-contained
- Verify: resulting binary runs on a machine with no Python installed

#### 5.2 Cross-Platform Verification
Run a complete playthrough on Windows, macOS, and Ubuntu:
- No import errors on any platform
- MIDI device enumeration returns devices correctly (`python-rtmidi` covers all three)
- Audio sync stays within ±50 ms of wall clock for the duration of a 3-minute song
- 60 FPS sustained on reference hardware (integrated GPU acceptable)

---

## Recommended Technology Decisions

| Concern | Current | Recommended |
|---|---|---|
| MIDI input | `pygame.midi` | `mido` + `python-rtmidi` backend |
| Audio | `ctypes` MCI (Windows only) | `pygame.mixer` (cross-platform) |
| Graphics | OpenGL 1.x immediate mode | Keep OpenGL (perspective camera is the core visual); refactor architecture coupling and replace `glDrawPixels` with pygame surface HUD overlay |
| MIDI simulation | `pyautogui` keyboard injection | Direct event consumption in game loop |
| Threading | Raw threads, no locks | Threads + `threading.Lock` or `queue.Queue` for inter-thread comms |
| Config | JSON, device-by-id | JSON, device-by-name, schema version |

The core language (Python) and core libraries (pygame, mido, PyOpenGL) are all the right choices and should be kept.

---

## Summary

The repository is a **well-structured but incomplete prototype**. It successfully proves out the hardest parts of the problem — MIDI input, MIDI file parsing, and 3D note visualization. However, it stalled before connecting those systems into an actual game loop. The three pieces (MIDI input, MIDI file → patterns, audio playback) exist as independent subsystems that never communicate.

The path forward is not a rewrite — it is an integration and completion effort. Most of the code is worth keeping. What's needed is:
1. A working audio sync clock (Phase 2.1)
2. Hit detection tied to that clock (Phase 2.2)
3. Demo mode — auto-play with perfect hits when no device is connected (Phase 2.5)
4. A song selection screen (Phase 3.1)
5. Keyboard size classification (Phase 2.6)
6. Cross-platform audio (Phase 1.4)

Items 1, 2, and 3 are tightly coupled: demo mode reuses the same `ScoringEngine` and `GameEngine` as normal play — the only difference is the input source. Building hit detection (item 2) essentially gives demo mode (item 3) for free.