# MidiMania

**English** · [简体中文](README.zh-CN.md)

A cross-platform, DJmax-style rhythm game. Notes fall from a vanishing point and
grow toward a judgment bar; you press the matching key as each note arrives. Every
chart is **auto-generated from a `.mid` file** — drop in a MIDI and play it, with a
PC keyboard, a real MIDI keyboard, or watch the built-in demo.

```
python mania.py
```

opens the song-selection menu over the `songs/` library in an OpenGL window.

---

## Features

- **Charts from MIDI.** Patterns are generated straight from a `.mid` (type 0/1).
  No hand-authored note maps.
- **Three ways to play:**
  - **PC Keyboard** — always available; the song's pitch range is compressed onto
    9 lanes (`A S D F Space J K L ;`).
  - **MIDI Keyboard** — once a device is detected and calibrated, notes map 1:1 to
    lanes, so chords stay distinct.
  - **Demo** — auto-plays at perfect timing (100% / S), for previewing a song or
    verifying your setup with no input device.
- **Auto keyboard sizing.** The MIDI's pitch range picks the smallest covering
  keyboard size (25 / 32 / 37 / 49 / 61 / 88 keys).
- **OpenGL vanishing-point renderer** with a neon arcade UI skin, an on-screen HUD
  (score, combo, accuracy), and a results screen with rank badges.
- **Audio that just works.** Plays a paired audio track if one ships with the
  chart; otherwise synthesizes a preview straight from the MIDI — so any song is
  playable with no shipped audio.
- **Audio-clock timing authority** with manual A/V offset, ±35 / 75 / 120 ms hit
  windows, and combo scoring.

---

## Requirements

- **Python 3.10+**
- An **OpenGL** driver
- On Linux, the platform MIDI backend for `python-rtmidi` (e.g. ALSA / JACK dev
  headers) and pygame system dependencies

Python dependencies (see [`requirements.txt`](requirements.txt)):

| Package | Role |
|---|---|
| `pygame` | Window, audio mixer, event loop, surface blitting |
| `mido` | MIDI file parsing |
| `python-rtmidi` | Live MIDI device input |
| `PyOpenGL` (+ `PyOpenGL_accelerate`) | Perspective renderer |

## Install

```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
```

## Run

**Song-selection menu** (default) over the `songs/` library:

```bash
python mania.py
python mania.py --songs path/to/library   # use a custom library directory
```

**Play one chart directly:**

```bash
python mania.py SONG.mid                   # auto-plays in demo mode
python mania.py SONG.mid --play            # take control with the PC keyboard
python mania.py SONG.mid --audio SONG.ogg  # use a specific audio track
python mania.py SONG.mid --mode pc         # 9-lane PC mode (default: midi, 1:1)
```

Audio precedence for a direct chart: `--audio` if given → a produced track paired
with the MIDI by name (`SONG.mid` → `SONG.ogg/.mp3/.wav/.flac` beside it) → else a
temporary WAV synthesized from the MIDI.

## Controls

**Menu:** ↑↓ pick a song · ←→ choose input mode (PC / Demo / MIDI) · `K` cycle
keys-mode · `M` open MIDI setup · `Enter` play · `Esc` quit.

**In a song:** play the lane keys (PC: `A S D F Space J K L ;`, or your MIDI
keyboard). `P` / `Space` pause · `Esc` back.

**After a song:** `Enter` return to the menu · `R` retry.

**MIDI keyboard setup:** press `M` in the menu, pick your device, then press your
**lowest** and **highest** keys to calibrate the span (a MIDI port can't report its
own key count). The measured span limits which keys-modes and songs are playable.

---

## Song package format

The menu scans `songs/` for one folder per song. A folder with no chart or an
unparseable / out-of-range MIDI is **skipped, not fatal**.

```
songs/<name>/
├── chart.mid                     # required (or the first *.mid in the folder)
├── meta.json                     # optional: { "title", "artist", "bpm" }
└── <name>.ogg|.mp3|.wav|.flac    # optional produced audio; else a synth preview
```

All `meta.json` fields are optional; an absent `title` falls back to the
prettified folder name. Bundled samples: `bach-cello`, `chords`, `heiwa-na-hibi`,
`twinkle`.

---

## Project layout

```
mania.py              # launcher / CLI entry point
src/
├── app.py            # screen flow: MENU → MIDI_SETUP → PLAYING → RESULTS
├── midi/             # parser (MIDI → notes), classifier (keyboard size), device (rtmidi I/O)
├── game/             # chart builder, engine (state machine), scoring, demo auto-play
├── audio/            # audio player (timing clock) + MIDI→WAV synth fallback
├── input/            # InputSignal currency + MIDI note→lane adapter
└── ui/               # OpenGL renderer, geometry, HUD, menu, results, MIDI setup, neon skin
songs/                # song library (one folder per song)
resources/            # UI assets (neon atlas)
tests/                # headless unit + flow tests (+ GL smoke tests)
ai-working-log/       # design docs, original-codebase report, per-feature specs, progress tracking
```

## Architecture in brief

`InputSignal(lane, time_ms)` is the shared input currency across PC, MIDI, and
demo sources. The **audio clock is the single timing authority** — the engine
stamps input timestamps from it, so heterogeneous event times can't corrupt the
judgments. The OpenGL scene is drawn first, then every 2D layer (menu, HUD,
countdown, results) is composited on top as a fullscreen textured quad. External
backends (rtmidi, the mixer, the synth) sit behind injectable seams with lazy
imports, so modules import and tests run with no hardware.

Notes live in world space via `note_z = (note.time_ms − current_ms) × UNITS_PER_MS`;
the perspective projection maps Z → screen Y. Placement math is pure and
unit-tested.

Full design rationale and decisions:
[`ai-working-log/DESIGN.md`](ai-working-log/DESIGN.md) ·
detailed per-feature specs in [`ai-working-log/specs/`](ai-working-log/specs/) ·
progress in [`ai-working-log/TRACKING.md`](ai-working-log/TRACKING.md).

## Testing

Tests run **headless** under SDL dummy video/audio drivers — the full core and UI
flow are verified with no display or audio device:

```bash
python -m pytest tests/
# or:  python -m unittest discover -s tests
```

The handful of GL smoke tests need a real OpenGL context and auto-skip under the
dummy driver / CI.

## Status

Phases 1–4 complete (foundation, game engine, UI & audio, MIDI device input);
Phase 5 polish in progress (neon arcade skin landed). Remaining work: combo/score
animation, a scrolling viewport for large keyboards (49key+), cross-platform
verification, and PyInstaller packaging. See
[`ai-working-log/TRACKING.md`](ai-working-log/TRACKING.md) for the per-feature
breakdown.

Out of scope for v1: online leaderboards, custom skins/themes, multiplayer, a note
editor, and video backgrounds.
