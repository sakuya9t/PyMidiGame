# MidiMania — Progress Tracking

## Goal

Rewrite PyMidiGame into **MidiMania**: a cross-platform, DJmax-style rhythm game
where notes fall from a vanishing point toward a hit bar and the player presses
the matching key as each note arrives.

Key requirements: MIDI keyboard input via `python-rtmidi`; patterns auto-generated
from a `.mid` (+ optional audio); keyboard size classified from the MIDI range;
OpenGL perspective renderer; demo mode when no device is connected; runs on
Windows/macOS/Linux.

Strategy, decisions, and architecture: [`ai-working-log/DESIGN.md`](ai-working-log/DESIGN.md).
Original-codebase analysis: [`ai-working-log/REPORT.md`](ai-working-log/REPORT.md).
Detailed per-feature design specs: [`ai-working-log/specs/`](ai-working-log/specs/).

---

## Phase Status

### Phase 1 — Foundation Cleanup
| # | Task | Status |
|---|------|--------|
| 1.1 | Fix `requirements.txt` (mido, rtmidi, PyOpenGL; drop pygame 1.9.6) | ✅ |
| 1.2 | Replace `pygame.midi` with `python-rtmidi` | ✅ |
| 1.3 | Remove `pyautogui` key simulation; wire MIDI to the game loop | ✅ |
| 1.4 | Replace Windows-MCI `Mp3Player` with `pygame.mixer` | ✅ |
| 1.5 | Delete the deprecated 2D `GameStageScene`; keep the GL renderer | ✅ |
| 1.6 | Thread-safe shared `Store` | ✅ |

### Phase 2 — Game Engine
| # | Task | Status |
|---|------|--------|
| 2.1 | `src/midi/parser.py` — MIDI → `NoteEvent` list (tempo map) | ✅ |
| 2.2 | `src/midi/classifier.py` — keyboard size from note range | ✅ |
| 2.3 | `src/game/chart.py` — chart builder, lane assignment | ✅ |
| 2.4 | `src/game/engine.py` — game loop, state machine | ✅ |
| 2.5 | `src/game/scoring.py` — hit windows, score, combo | ✅ |
| 2.6 | `src/game/demo.py` — perfect-timing auto-play | ✅ |

### Phase 3 — UI & Audio
| # | Task | Status |
|---|------|--------|
| 3.1 | `pygame.mixer` audio synced to the game clock | ✅ |
| 3.2 | Song-selection screen + menu→play→results loop | ✅ |
| 3.3 | OpenGL vanishing-point renderer (atlas-textured) | ✅ |
| 3.4 | HUD overlay (score, combo, accuracy, DEMO badge) | ✅ |
| 3.5 | Results screen (rank, score, accuracy, breakdown) | ✅ |

### Phase 4 — MIDI Device Input
| # | Task | Status |
|---|------|--------|
| 4.1 | `src/midi/device.py` — list/open/poll/parse ports | ✅ |
| 4.2 | `src/input/midi_input.py` — note_on → lane | ✅ |
| 4.3 | `src/ui/midi_setup.py` — device select + span calibration | ✅ |
| 4.4 | Menu keys-mode + device line + per-song playability | ✅ |
| 4.5 | App wiring: MIDI_SETUP screen, frame-polled play loop | ✅ |

### Phase 5 — Polish (not started)
Hit effects · combo animation · large-keyboard scrolling viewport (49key+) ·
cross-platform verification · PyInstaller packaging. See DESIGN.md → *Remaining /
Future Work*.

> **▶ Playable now:** `python mania.py` opens the **song-selection menu** over
> `songs/` in an OpenGL window (↑↓ pick · ←→ PC / Demo / MIDI · K keys-mode · M
> MIDI setup · Enter play · Esc quit; after a song, Enter→menu, R→retry). Plug in a
> **MIDI keyboard**, press `M` to select and calibrate it (press lowest + highest
> key), then play with real keys. `python mania.py SONG.mid` plays one chart
> directly (`--play` for PC keyboard, P pause, Esc back).

**Suite: 323 tests headless · 0 failures · 8 skip (GL smoke tests — need a real
OpenGL context).**

---

## Decisions Log

Condensed from session history; the detailed reasoning lives in the linked specs.

- **Phase 1 — foundation.** Stripped `pygame.midi` / `pyautogui` / Windows-MCI from
  the legacy code and swapped in rtmidi + `pygame.mixer`; deleted the 2D scene;
  added a `Lock` to the shared `Store`. (These were pre-rewrite shims on the old
  tree, which was later removed — see Cleanup below.)
- **2.1 parser.** mido; type 0/1 only, **type 2 rejected** (independent timelines);
  tempo map across mid-file changes. Added a type-0 fixture (Bach cello) beside
  twinkle.
- **2.2 classifier.** Smallest covering size; **notes outside `[21,108]` →
  `ValueError`** (no silent 88-key fallback).
- **2.3 chart builder** ([spec](ai-working-log/specs/2026-05-04-chart-builder-design.md)).
  MIDI 1:1; **PC range → 9 lanes** by linear interpolation, half-up rounding;
  range-validate both modes.
- **2.4 engine** ([spec](ai-working-log/specs/2026-06-02-game-engine-design.md)).
  **Injected `Clock`/`Scoring`/`DemoSource` Protocols** (engine never constructs
  deps → built/tested before them); countdown via a `dt` accumulator; **finish at
  chart tail** with cached time; engine owns input timestamps.
- **2.5 scoring.** ±35/75/120 ms windows; `base = 1e6/total` ×1.0/0.7/0.4;
  nearest-match, a stray press is a MISS that consumes no note, `tick()` is the
  authoritative miss; ranks S/A/B/C/D.
- **2.6 demo.** Pops due notes as perfect signals → 1e6 / 100% / S; proven
  end-to-end headless against the real core.
- **3.1 audio.** **Wall-clock authority** (not the backend's position query),
  pause-excluded, `AUDIO_OFFSET_MS`; rtmidi and mixer behind injectable backends.
- **3.2 menu + app flow** ([spec](ai-working-log/specs/2026-06-06-song-select-design.md)).
  MENU → PLAYING → RESULTS loop in one window; scan `songs/` and **skip
  unparseable folders, not fatal**; PC vs Demo modes.
- **3.3–3.5 OpenGL renderer** ([spec](ai-working-log/specs/2026-06-07-opengl-renderer-design.md)).
  Vanishing-point GL scene + **surface→texture HUD compositing** (retired
  `glDrawPixels`); **texture-first** atlas via a single `_textured_quad` seam for
  future FX; pure unit-tested geometry; standalone results screen.
- **4.x MIDI input** ([spec](ai-working-log/specs/2026-06-07-midi-device-input-design.md)).
  **Frame-polling** rtmidi (not a callback thread); **span calibration by pressing
  lowest/highest** (a port can't report its key count); menu keys-mode limited to
  the measured span with per-song playability tags.
- **Cleanup (legacy removal).** With the rewrite self-contained, deleted the 2020
  PyMidiGame tree (28 files: old entry point, `controllers/`, legacy `ui/`,
  `config/`, `settings/`, `midi/`, `logger/`, `Mp3Player/`, and the Phase-1 shim
  test). Promoted the two stray sample MIDIs into the library:
  `resources/chords.mid` → `songs/chords/` and `resources/平和な日々.mid` →
  `songs/heiwa-na-hibi/`. Kept the neon atlas.
