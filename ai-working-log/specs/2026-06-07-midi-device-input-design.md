# MIDI Device Input + Setup/Calibration + Keys Mode

**Date:** 2026-06-07
**Status:** Design (approved in conversation; proceed incrementally)
**Related:** DESIGN.md §10 (MIDI device I/O), §12 (MIDI input adapter), §14 (menu device select)

---

## 1. Goal

Let a player play with a real MIDI keyboard. Today the menu hard-codes MIDI as
disabled (`SELECTABLE_MODES = ('pc','demo')`) and never probes for devices, so a
connected keyboard shows "(no device)". Implement:

1. **Device selection UI** — choose which MIDI input port to play on.
2. **Connection test = calibration** — press the lowest then the highest key;
   this confirms input is received *and* measures the device's playable span.
3. **Keys-mode selector in the main menu** — `AUTO` or a fixed size
   (25/32/37/49/61/88), constrained to the device's measured span, so the
   playfield mirrors the physical keyboard.
4. **MIDI play** — selecting MIDI + a song opens the port and routes presses to
   the engine.

## 2. Key technical finding

`python-rtmidi` enumeration returns only port **names** (here: `Focusrite USB
MIDI 0`, `Oxygen Pro 49 1`, `MIDIIN2 (Oxygen Pro 49) 2`, …). There is **no
reliable way to query a controller's key count** (no standard MIDI message; the
"49" in a name is a non-portable hint, and the trailing integer is the Windows
port index). Therefore the **press-lowest/highest calibration is the source of
truth** for the span. A best-effort name digit may pre-fill the display only.

## 3. Decisions

| # | Decision |
|---|----------|
| D1 | Span measured by calibration (press lowest + highest), not detected from the port |
| D2 | Calibration **is** the connection test (receiving the presses proves the link) |
| D3 | Keys-mode options limited to sizes whose MIDI range ⊆ the measured span |
| D4 | A song is playable in MIDI mode iff its note range fits the effective keyboard; non-fitting songs are shown but not startable in MIDI mode (no transpose) |
| D5 | Input timing v1: poll the port each frame (drain the queue). Latency ≤ one frame (~16 ms); good for GREAT/GOOD. Upgrade path: rtmidi callback timestamping (no engine/scoring change) |
| D6 | rtmidi behind an injectable backend; lazy import — modules import & unit-test headlessly with a fake device |
| D7 | note_off ignored for v1 (taps only); hold-release is a later refinement |

## 4. Components

### 4.1 `src/midi/device.py` — device I/O
```python
def list_input_ports(backend=None) -> list[str]: ...

@dataclass
class MidiMsg:
    kind: str        # 'note_on' | 'note_off' | 'other'
    note: int
    velocity: int

class MidiInputDevice:
    def __init__(self, backend=None): ...          # lazy rtmidi backend
    def open(self, port_index: int) -> None: ...
    def close(self) -> None: ...
    def poll(self) -> list[MidiMsg]: ...           # drain get_message(); parse

def guess_key_count(port_name: str) -> int | None  # weak name hint, display only
```
A `note_on` with velocity 0 is normalized to `note_off` (running-status
convention), matching the existing `midis2events` logic.

### 4.2 `src/input/midi_input.py` — input adapter
```python
class MidiInput:
    def __init__(self, device: MidiInputDevice, midi_low: int): ...
    def poll(self) -> list[InputSignal]:
        # note_on (vel>0) within range -> InputSignal(lane = note - midi_low)
        # out-of-range notes ignored; note_off ignored (v1 taps)
```
The engine stamps the time (`handle_input` reads `clock.current_ms()`), so the
adapter only carries the lane.

### 4.3 `src/ui/midi_setup.py` — setup + calibration screen
A small state machine drawn to a surface (presented over GL like the menu):

```
SELECT_DEVICE → CALIBRATE_LOW → CALIBRATE_HIGH → DONE
```
- **SELECT_DEVICE:** list ports (↑↓), Enter opens the port → CALIBRATE_LOW. Shows
  the name hint. Esc cancels to menu.
- **CALIBRATE_LOW:** "Press your LOWEST key." First `note_on` captures `min_note`
  (echoes e.g. "C2 (36)") → CALIBRATE_HIGH. (Live echo = connection test.)
- **CALIBRATE_HIGH:** "Press your HIGHEST key." `note_on > min_note` captures
  `max_note` → DONE.
- **DONE:** "Detected N keys (C2–C6).  Enter save · R redo." Enter saves
  `(port_index, port_name, min_note, max_note)` and returns to the menu; R
  restarts calibration; Esc cancels.

`handle(event, midi_msgs)` advances the machine from key events + polled MIDI;
`render(surface)` draws the current step. Pure logic is unit-tested by feeding
synthetic `MidiMsg`s (no hardware).

### 4.4 Menu additions (`src/ui/menu.py`)
- A **settings footer**: `Mode` (←→, now includes `MIDI` when a device is
  configured), `Keys` (cycle with `K`: AUTO + sizes ⊆ span), `Device`
  (`M` opens MIDI Setup; shows configured port + measured span or "none").
- Per-song MIDI playability badge when MIDI mode is selected (✓ / ✗ needs N).
- New action types: `OpenMidiSetup`, plus existing `StartGame` extended with the
  resolved keyboard class.

### 4.5 App / chart wiring (`src/app.py`, `src/game/chart.py`)
- `build_chart(midi_path, mode, kb_override=None)` — when `kb_override` is given,
  use it instead of `classify()`; range validation already raises if a note is
  out of the kb range (caller pre-checks for playability).
- `App` holds `_midi_config` (port + span) and `_keys_mode`. New
  `AppScreen.MIDI_SETUP`.
- `start_game(entry, 'midi')`: resolve kb (fixed size or AUTO-within-span),
  `build_chart(..., kb_override=kb)`, real engine (`demo=False`), open the
  device, wrap in `MidiInput`. Each frame: `for sig in midi_input.poll():
  engine.handle_input(sig.lane)`.
- The single-song `run()` path unchanged (keyboard/demo only) for now.

## 5. Effective-keyboard resolution

`KEYBOARD_CLASSES` (the classifier table: 25/32/37/49/61/88 with their
`midi_low/high`). Given device span `[lo, hi]`:
- **Keys-mode = AUTO:** kb = `classify(song notes)`; playable iff that class's
  range ⊆ `[lo, hi]`.
- **Keys-mode = fixed size S:** kb = the class named S; selectable only if S's
  range ⊆ `[lo, hi]`; song playable iff its notes ⊆ S's range.

No device configured → keys-mode shows `AUTO` only and MIDI mode is unavailable
(unchanged from today, but now because no port is *configured*, having probed).

## 6. Testing

Headless, with a **FakeMidiBackend** feeding scripted messages:
- `test_midi_device.py` — port listing; open/poll/close; note_on/off parsing;
  velocity-0 → note_off; name hint.
- `test_midi_input.py` — note_on→InputSignal lane math; range filtering; note_off
  ignored.
- `test_midi_setup.py` — the SELECT→LOW→HIGH→DONE state machine driven by
  synthetic `MidiMsg`s (captures span, redo, cancel, high≤low rejected).
- `test_menu` additions — keys-mode cycling constrained to span; MIDI mode
  appears only when configured; per-song playability.
- `test_app_flow` additions — MIDI_SETUP transitions; MIDI run routes polled
  signals into scoring (drive with a fake device).
- Real-hardware verification is manual (the user plays); the GL setup/menu
  screens get the offscreen-screenshot check.

## 7. Milestones (a commit each)

1. `src/midi/device.py` + tests (device I/O, parsing, name hint).
2. `src/input/midi_input.py` + tests (adapter).
3. `src/ui/midi_setup.py` + tests (setup/calibration state machine), render.
4. Menu keys-mode + device line + MIDI-mode enablement + playability + tests.
5. App wiring: `AppScreen.MIDI_SETUP`, `build_chart(kb_override)`, MIDI play
   loop; verify screenshots + report; update TRACKING/DESIGN.

## 8. Out of scope (now)
- Hold-note release via note_off; sustain pedal; velocity-sensitive scoring.
- Persisting the MIDI config to `config.json` across runs (in-session only v1;
  easy follow-up).
- Callback-based low-latency timestamping (D5 upgrade path).
- Large-keyboard scrolling viewport (DESIGN Phase 5.3) — 49+ lanes still render
  full-width for now.
