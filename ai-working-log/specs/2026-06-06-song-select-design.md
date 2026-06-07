# Phase 3.2 — Song Selection Screen + App Flow — Design Spec

**Date:** 2026-06-06
**Status:** Approved (brainstormed)
**Tracking:** TRACKING.md Phase 3.2
**Depends on:** Phase 2.4 engine, 2.5 scoring, 2.6 demo, 3.1 audio, 3.3 renderer (all done)

---

## Goal

Turn MidiMania from a CLI launcher that plays one chart into a navigable game:
browse a `songs/` library, pick a song and input mode, play, see results, and
return to the menu — all inside the single pygame window, without restarting the
process.

This completes the **menu → play → results → menu** loop (DESIGN.md §14, §15)
and is the explicit next Todo in TRACKING.md (3.2).

### In scope
- A `songs/` library scanner producing displayable song metadata.
- A `SongMenu` screen: list songs, show metadata, pick an input mode, confirm.
- An app-level state machine (`AppScreen`: MENU / PLAYING / RESULTS) that owns
  the window + loop and transitions between screens, re-loading the engine per
  song.
- Seed `songs/` with sample folders built from the existing test fixtures.

### Out of scope (separate threads)
- **Real MIDI device input** (`src/midi/device.py`, MIDI input handler). The menu
  shows a **MIDI Keyboard** option but it is **disabled/greyed-out** with a "no
  device" note. Only **PC Keyboard** and **Demo** are selectable.
- **OpenGL perspective port** (DESIGN §13) — the 2D renderer is reused as-is.
- **Standalone results screen** (3.5). RESULTS reuses the renderer's existing
  `_draw_results` overlay; this increment only adds retry/menu navigation around
  it.

---

## Architecture

Approach A — a lightweight app state machine, no new framework. Mirrors the
engine's enum-driven style and the codebase's injection-for-headless-testing
convention (every prior phase has a headless smoke test).

```
mania.py ──> App(songs_dir)        # new top-level loop owner
                │
   ┌────────────┼─────────────────────────────┐
 MENU         PLAYING                       RESULTS
SongMenu   GameEngine + Renderer        Renderer (FINISHED overlay)
   │          ▲   ▲                          │
scan_songs    │   └ build_chart / make_audio │
   │          └ make_engine (demo flag)      │
   └────────── StartGame(entry, input_mode) ─┘
```

Transitions:

```
MENU --StartGame(entry, mode)--> PLAYING
MENU --QuitGame / QUIT---------> (exit)
PLAYING --engine.is_finished()-> RESULTS
PLAYING --Esc-----------------> MENU         (abandon song)
PLAYING --P-------------------> pause/resume (in place)
RESULTS --R-------------------> PLAYING       (retry same song+mode)
RESULTS --Enter/Esc-----------> MENU
```

---

## Components

### 1. `src/ui/menu.py`

#### `SongEntry` (dataclass)
One scanned song, all fields display-ready:
```python
@dataclass
class SongEntry:
    name: str                 # directory name (stable id)
    dir: str                  # path to the song folder
    midi_path: str            # chart .mid
    audio_path: str | None    # produced audio beside the MIDI, else None
    title: str                # meta.json title, else prettified dir name
    artist: str               # meta.json artist, else ""
    key_class: str            # classified keyboard size, e.g. "32key"
    total_duration_ms: float  # max(time_ms + duration_ms) across notes
    bpm: float | None         # meta.json bpm, else None (not derived from MIDI in v1)
```

#### `scan_songs(songs_dir, *, exists=os.path.exists) -> list[SongEntry]`
- Iterate immediate subdirectories of `songs_dir`, sorted by name.
- Find the chart file: prefer `chart.mid`; else the first `*.mid`/`*.midi` (sorted).
  A folder with no chart file is skipped.
- Parse + classify the chart (`MidiParser.parse` → `classify`) to compute
  `key_class` and `total_duration_ms`. **Any parse/classify error skips that
  folder** — one bad MIDI must not break the whole scan.
- Resolve `audio_path` via the existing `resolve_audio_source` logic, but only
  accept a *produced* sibling (not the MIDI itself); `None` means "synthesize at
  play time" (the existing `make_audio` fallback).
- Read optional `meta.json` (`title`, `artist`, `bpm`); missing file or bad JSON
  → defaults (title = dir name, artist = "", bpm = None).
- A non-existent or empty `songs_dir` → `[]`.

#### Input-mode model
Module constants for the three modes; `SELECTABLE_MODES = ("pc", "demo")`,
`"midi"` shown but disabled. The menu cycles only the selectable modes.

#### Result types (what `handle_event` returns)
```python
@dataclass
class StartGame:
    entry: SongEntry
    input_mode: str   # "pc" or "demo"

class QuitGame: ...   # marker
```

#### `SongMenu`
```python
class SongMenu:
    def __init__(self, songs: list[SongEntry], size: tuple[int, int]): ...
    def handle_event(self, event) -> StartGame | QuitGame | None: ...
    def render(self, target: pygame.Surface) -> None: ...
```
- State: `songs`, `selected_index` (0), `mode_index` over `SELECTABLE_MODES` (0 = "pc").
- `handle_event` (KEYDOWN):
  - `UP`/`DOWN`: move selection, clamped to `[0, len-1]` (no wrap; no-op on empty).
  - `LEFT`/`RIGHT`: cycle `mode_index` across `SELECTABLE_MODES` (wraps).
  - `RETURN`: emit `StartGame(songs[selected_index], SELECTABLE_MODES[mode_index])`;
    **no-op (returns None) when the library is empty**.
  - `ESCAPE`: emit `QuitGame`.
  - otherwise `None`.
- `render`: title bar; the song list with the selected row highlighted; a detail
  line for the selected song (title · artist · key_class · m:ss duration); the
  input-mode selector with the active mode highlighted and **MIDI greyed-out with
  a "no device" note**; footer key hints (↑↓ select · ←→ mode · Enter play ·
  Esc quit). Empty library → a centered "No songs found — add a folder under
  songs/ with a chart.mid." message; mode selector still drawn.

Rendering targets a `pygame.Surface`, so it runs under SDL's dummy driver
headlessly (same pattern as `Renderer`).

### 2. `src/app.py` (extended)

Keep the existing helpers (`build_chart`, `make_engine`, `build_keymap`,
`make_audio`, `resolve_audio_source`, `SIZE`). Add:

```python
class AppScreen(Enum):
    MENU = auto(); PLAYING = auto(); RESULTS = auto()

class App:
    def __init__(self, songs_dir="songs", size=SIZE, *, surface=None,
                 scan=scan_songs, audio_factory=None): ...
    # transitions (pure of the pygame event loop; unit-testable)
    def start_game(self, entry: SongEntry, input_mode: str) -> None
    def to_menu(self) -> None
    def retry(self) -> None
    # per-frame
    def handle_event(self, event) -> None
    def update(self, dt_ms: float) -> None
    def render(self) -> None
    def step(self, dt_ms: float, events) -> bool   # returns still-running
    def run(self) -> None                          # real pygame loop over step()
```

- `audio_factory(entry, chart) -> Clock` defaults to
  `make_audio(entry.midi_path, entry.audio_path, chart=chart)`. Injecting it lets
  the headless test supply a controllable manual clock to fast-forward to FINISHED.
- `start_game`: `demo = input_mode == "demo"`; `chart_mode = "midi" if demo else "pc"`
  (PC Keyboard plays compressed lanes; Demo auto-plays the full-fidelity layout);
  build chart → `audio_factory` → `make_engine(chart, clock, demo=demo)` →
  `build_keymap(chart.lane_count)`; store `(entry, input_mode)` for retry;
  `engine.start()`; screen = PLAYING.
- `handle_event` dispatch by screen:
  - MENU: forward to `SongMenu`; `StartGame` → `start_game`; `QuitGame` → stop.
  - PLAYING: `Esc` → `to_menu`; `P` → engine pause/resume; lane keys (via keymap)
    → `engine.handle_input` (only when not demo, matching current `run()`).
  - RESULTS: `R` → `retry`; `Enter`/`Esc` → `to_menu`.
- `update`: in PLAYING, `engine.update(dt_ms)`; if `engine.is_finished()` →
  screen = RESULTS. No-op otherwise.
- `render`: MENU → `menu.render`; PLAYING/RESULTS → `renderer.render(...,
  state=engine.state, ...)` (FINISHED draws the results overlay automatically).
- `step`: drain provided events (QUIT → stop), `update`, `render`, return running.
- `run`: `pygame.init`, `set_mode`, `Clock.tick(60)` loop calling `step` with
  real `pygame.event.get()`, then `display.flip()`; `pygame.quit()` on exit.

`mania.py` gains a no-arg / `--songs DIR` path that launches `App(...).run()`;
the existing `SONG.mid` positional path still works (direct single-song run).

### 3. Seeded `songs/` library

Create real folders from the fixtures so the menu has content and the game runs
end-to-end out of the box:
```
songs/
  twinkle/    chart.mid (copy of tests/fixtures/twinkle.mid)   + meta.json
  bach-cello/ chart.mid (copy of bach-cello-type0.mid)         + meta.json
```
`meta.json`: `{ "title", "artist", "bpm" }`. No produced audio is shipped → the
MIDI-synth WAV fallback supplies preview audio (already implemented).

---

## Error handling
- Empty / missing `songs/` → menu shows the empty state; `RETURN` is a no-op.
- A song folder with no chart, or an unparseable MIDI → silently skipped by
  `scan_songs` (logged to stdout, consistent with the app's other degradations).
- Audio still degrades to silent via the existing `make_audio` path.

## Testing (TDD, headless under SDL dummy drivers)
- `tests/test_song_menu.py`
  - `scan_songs`: seeded `songs/` → entries with expected title/key_class/order;
    `meta.json` override vs. defaults; folder without a chart skipped; malformed
    MIDI skipped; empty/missing dir → `[]` (temp dirs + copied fixtures).
  - `SongMenu`: up/down clamps; left/right cycles modes (wraps, skips MIDI);
    `RETURN` → `StartGame` with correct entry + mode; `ESCAPE` → `QuitGame`;
    empty library `RETURN` → `None`; headless `render` smoke for populated + empty.
- `tests/test_app_flow.py`
  - `App` with injected manual-clock `audio_factory` over a temp/seeded library:
    drive MENU `RETURN` (demo) → PLAYING; advance `dt` past countdown; advance
    clock past finish → `update` flips to RESULTS at score 1,000,000 / acc 1.0;
    RESULTS `Enter` → MENU; RESULTS `R` → PLAYING; `QUIT` event stops `step`.

Whole suite stays green (currently 227 tests, 1 skip).

---

## Verification
1. `python -m unittest discover tests` → all green, new tests included.
2. `python mania.py` → song list with twinkle + bach-cello; ↑↓ selects; ←→ toggles
   PC/Demo (MIDI greyed); Enter on Demo auto-plays to a 1,000,000 / S result;
   Enter returns to the menu; R retries; Esc from the menu quits.
