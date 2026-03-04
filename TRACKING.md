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
| 2.1 | `src/midi/parser.py` — MIDI file → `NoteEvent` list (ticks → ms, tempo map) | ✅ Done |
| 2.2 | `src/midi/classifier.py` — detect keyboard size class from note range | ✅ Done |
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

### Session 4 (this session)
**Completed Phase 2.1–2.2; added type-0 MIDI fixture**

Phase 2.1 — MIDI file parser (`src/midi/parser.py`):
- `NoteEvent` dataclass: `note`, `time_ms`, `duration_ms`, `channel`, `velocity`
- `MidiParser.parse(path)`: reads any MIDI type (0/1/2); builds tempo map from all `set_tempo` messages; converts ticks → ms with correct mid-file tempo change support; pairs `note_on`/`note_off` (including velocity-0 note_on convention) for duration; strips velocity-0 events; returns list sorted by `time_ms`
- Key bug fixed during development: guard `if msg.type not in ('note_on', 'note_off'): continue` prevents `AttributeError` on control_change/program_change messages
- `tests/test_midi_parser.py`: 36 tests across 5 classes:
  - `TestNoteEventDataclass` — field access, equality, required args
  - `TestMidiParserSynthetic` — single note timing (120 BPM), duration, beat-offset, velocity-0-as-noteoff, two sequential notes, field preservation, mid-file tempo change
  - `TestMidiParserType1` — type-1 multi-track merge: notes from two tracks at different ticks merge into single sorted list
  - `TestMidiParserWithFixture` — integration against `tests/fixtures/twinkle.mid`: list type, nonzero count, all velocities > 0, all durations > 0, all times ≥ 0, sorted order, first note at 0 ms, first note duration ≈ 601.97 ms (verified against mido tempo calculation), note/channel bounds
  - `TestMidiParserWithType0Fixture` — integration against `tests/fixtures/bach-cello-type0.mid`: confirms file is type=0/tracks=1, 656 events, all velocities/durations positive, sorted, first note G2 (note=43, vel=77, dur≈196 ms), single channel (ch=0), note range C2–G4 (36–67), tempo accumulation verified (events beyond 10 s exist), round-trip note count matches source

Phase 2.2 — Keyboard size classifier (`src/midi/classifier.py`):
- `KeyboardClass` dataclass: `name`, `key_count`, `midi_low`, `midi_high`, `lane_count`
- `classify(notes)`: finds `min_note`/`max_note`; iterates class table smallest-first; returns first class covering `[min_note, max_note]`; empty list → `25key`; out-of-range fallback → `88key`
- Keyboard table: `25key` (48–72), `32key` (41–72), `37key` (41–77), `49key` (36–84), `61key` (36–96), `88key` (21–108)
- `tests/test_midi_classifier.py`: 22 tests across 5 classes:
  - `TestKeyboardClassDataclass` — fields, equality, required args
  - `TestClassifyExactBoundaries` — each of the 6 classes by exact boundary note pair
  - `TestClassifySmallestFit` — notes fitting inside each class but not the one below
  - `TestClassifyReturnFields` — correct `key_count`, `midi_low`, `midi_high`, `lane_count` returned
  - `TestLaneIndexFormula` — `lane = note - midi_low` formula: lane 0 for lowest, `key_count-1` for highest, all notes in a 25key range produce valid indices
  - `TestClassifyEdgeCases` — single note, empty list

Type-0 fixture — `tests/fixtures/bach-cello-type0.mid`:
- Source: Bach Cello Suite No. 1 (mfiles.co.uk), originally a type-1 file with a tempo-map track and a note track
- Converted to type 0 using `mido.merge_tracks(m.tracks)` which interleaves all messages into a single track in absolute-tick order
- Properties: type=0, 1 track, 656 notes, channel 0 only, note range C2–G4 (36–67), 16 distinct tempos, ~130 s total
- Provides a case distinct from `twinkle.mid`: type-0 format, interleaved tempo changes, longer melody, 49-key keyboard class
- Temporary search files (`test2.mid`, `test-bitmidi.mid`, `twinkle-type0.mid`) removed after fixture was created

**Manual verification steps:**
1. Run `python -m unittest discover tests` from the project root → should report 94 tests, 0 failures (1 skip)
2. In a Python REPL from the project root:
   ```python
   import sys; sys.path.insert(0, '.')
   from src.midi.parser import MidiParser
   # twinkle.mid (type 1, Greensleeves)
   events = MidiParser.parse('tests/fixtures/twinkle.mid')
   print(len(events), events[0])   # ~90 events, NoteEvent(note=48, time_ms=0.0, ...)
   from src.midi.classifier import classify
   kb = classify(events)
   print(kb)                        # KeyboardClass(name='32key', ...)
   print(kb.midi_low, kb.midi_high) # 41 72
   # bach-cello-type0.mid (type 0, Bach Cello Suite No. 1)
   events2 = MidiParser.parse('tests/fixtures/bach-cello-type0.mid')
   print(len(events2), events2[0])  # 656 events, NoteEvent(note=43, time_ms=0.0, ...)
   kb2 = classify(events2)
   print(kb2)                       # KeyboardClass(name='49key', ...)
   print(kb2.midi_low, kb2.midi_high) # 36 84
   ```
3. Verify lane formula for first note of each fixture:
   ```python
   print(events[0].note - kb.midi_low)   # should be >= 0 and < kb.key_count
   print(events2[0].note - kb2.midi_low) # should be >= 0 and < kb2.key_count
   ```

---

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