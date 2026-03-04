# MidiMania — Progress Tracking

## Goal

Rewrite PyMidiGame into **MidiMania**: a cross-platform, DJmax-style rhythm game where note patterns fall from a vanishing point and grow toward a hit bar at the bottom. The player presses the matching key as each note arrives.

Key requirements:
- MIDI keyboard input via `python-rtmidi` (low latency, cross-platform)
- Patterns auto-generated from a `.mid` file + paired audio file
- Keyboard size classified from MIDI range (25/37/49/61/88 key)
- OpenGL perspective renderer (already working in old codebase — keep it)
- Demo mode when no MIDI device is connected (auto-plays with perfect timing)
- Cross-platform: Windows, macOS, Linux

Full specification: [`ai-working-log/DESIGN.md`](ai-working-log/DESIGN.md)
Codebase analysis: [`ai-working-log/REPORT.md`](ai-working-log/REPORT.md)

---

## Phase 1 — Foundation Cleanup

| # | Task | Status |
|---|------|--------|
| 1.1 | Fix `requirements.txt` (add mido, rtmidi, PyOpenGL; remove pygame 1.9.6) | ✅ Done |
| 1.2 | Remove `pygame.midi`, replace with `python-rtmidi` throughout | ✅ Done |
| 1.3 | Remove `pyautogui` keyboard simulation; wire MIDI events directly to game loop | ✅ Done |
| 1.4 | Replace `Mp3Player` (Windows-only MCI) with `pygame.mixer` | ✅ Done |
| 1.5 | Delete deprecated `GameStageScene.py` (2D scene); keep OpenGL renderer | ✅ Done |
| 1.6 | Add thread safety (`threading.Lock` or `queue.Queue`) to shared `Store` | ✅ Done |

## Phase 2 — Game Engine

| # | Task | Status |
|---|------|--------|
| 2.1 | `src/midi/parser.py` — MIDI file → `NoteEvent` list (ticks → ms, tempo map) | ⬜ Todo |
| 2.2 | `src/midi/classifier.py` — detect keyboard size class from note range | ⬜ Todo |
| 2.3 | `src/game/chart.py` + `note.py` — `NoteEvent` list → lane-assigned `Note` list | ⬜ Todo |
| 2.4 | `src/game/engine.py` — game loop, state machine, scroll position | ⬜ Todo |
| 2.5 | `src/game/scoring.py` — hit windows (PERFECT/GREAT/GOOD/MISS), score, combo | ⬜ Todo |
| 2.6 | `src/game/demo.py` — DemoPlayer auto-hits all notes at perfect timing | ⬜ Todo |

## Phase 3 — UI & Audio

| # | Task | Status |
|---|------|--------|
| 3.1 | Wire `pygame.mixer` audio: load, play, sync position to game clock | ⬜ Todo |
| 3.2 | Song selection screen (browse `songs/` directory) | ⬜ Todo |
| 3.3 | Refactor OpenGL renderer: decouple from `Store`, fix `glDrawPixels` → pygame surface blit | ⬜ Todo |
| 3.4 | HUD overlay (score, combo, accuracy, DEMO badge) rendered as pygame surface over GL frame | ⬜ Todo |
| 3.5 | Results screen (grade, score, accuracy, hit breakdown) | ⬜ Todo |

---

## Session Log

### Session 1 (prior)
- Generated `ai-working-log/REPORT.md`: full analysis of original codebase, identified 11 critical problems
- Fixed `requirements.txt`: upgraded pygame to 2.x, added mido, python-rtmidi, PyOpenGL
- Fixed `InputController.py` bug: missing `initial=False` parameter default
- Wrote `ai-working-log/DESIGN.md`: full redesign specification for MidiMania
- Decided to keep PyOpenGL renderer (perspective projection already works; pygame 2D cannot replicate vanishing-point effect without manual math)

### Session 3 (this session)
**Completed Phase 1.3–1.6**

Phase 1.3 — Remove `pyautogui` keyboard simulation:
- `KeyCodeConstants.py`: removed `import pyautogui`; dropped `pyautogui.KEY_NAMES` initializer; replaced with plain dict literal; `get_key_code()` now returns `None` for unknown keys via `dict.get()`
- `KeyMapper.py`: dropped all pyautogui imports and `pyautogui.PAUSE = 0`; `map_midi()` now posts `pygame.KEYDOWN`/`pygame.KEYUP` events directly via `pygame.event.post()`; MIDI input reaches the game loop as native pygame events without OS-level keyboard simulation

Phase 1.4 — Replace `Mp3Player` with `pygame.mixer`:
- `Mp3Player/__init__.py`: full rewrite using `pygame.mixer.music`; cross-platform (Windows/macOS/Linux); public API preserved (`play/pause/unpause/stop/isplaying/ispaused/volume/milliseconds/seconds`)
- `Mp3Player/windows.py`: deleted (Windows MCI implementation)
- `Mp3Player/readme.txt`: deleted

Phase 1.5 — Delete deprecated `GameStageScene.py`:
- `ui/scenes/GameStageScene.py`: deleted (2D renderer, superseded by OpenGL renderer)
- `ui/GameDisplay.py`: removed `GameStageScene` import; `render()` is a no-op stub pending Phase 3.3

Phase 1.6 — Thread safety for `Store`:
- `controllers/__init__.py`: added `threading.Lock`; `get()` and `put()` protected with `with self._lock`; also simplified `get()` using `dict.get()`

### Session 2 (this commit)
**Completed Phase 1.2: remove `pygame.midi`, replace with `python-rtmidi`**

Files changed:
- `midis2events.py` — full rewrite: removed `pygame.event.Event` creation; added `rtmidi_msg_to_event(msg_bytes)` that parses raw rtmidi byte lists using standard MIDI status nibbles; updated `simplify_midi_event` to work with plain dicts
- `InputQueue.py` — `InputMidiQueue.run()`: replaced `poll()` + `read(40)` with `get_message()` (rtmidi polling API); replaced `midi_input.close()` with `close_port()`
- `settings/MidiDeviceSettings.py` — removed both pygame_midi and unused rtmidi.midiutil imports; reduced to a minimal `midi_input = None` holder
- `controllers/InputController.py` — replaced `pygame_midi.Input(device_id)` with `rtmidi.MidiIn(); open_port(device_id - 1)`
- `controllers/GameController.py` — removed `pygame_midi` import and `pygame_midi.init()` call

Tests added (`tests/`):
- `tests/test_midis2events.py` — 36 tests across 4 classes:
  - `TestRtmidiMsgToEvent` — pure byte-parser tests (all MIDI types, missing-byte defaults, channel extraction)
  - `TestSimplifyMidiEvent` — velocity→EVENT_KEY_DOWN/UP logic with mocked key name lookup
  - `TestNoPygameMidiImport` — regression guard: midis2events must not expose `pygame` attribute
  - `TestRealMidiFile` — integration: loads `tests/fixtures/twinkle.mid` (real file from mfiles.co.uk, 189 messages), feeds every message's raw bytes through `rtmidi_msg_to_event`, cross-validates all fields against mido's independent parse; also runs the full `→ simplify_midi_event` pipeline and spot-checks 7 note-number-to-key-name mappings against `config.json`