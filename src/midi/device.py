"""
src/midi/device.py — MIDI input device I/O (python-rtmidi).

Lists input ports, opens one, and drains incoming messages into parsed `MidiMsg`
values. rtmidi sits behind an injectable backend (lazy import), so this module
imports and unit-tests headlessly with a fake backend — no hardware or rtmidi
required at import time.

Note: MIDI port enumeration exposes only port names, not key counts. There is no
reliable way to query how many keys a controller has, so the playable span is
measured by calibration in the MIDI setup screen (press lowest + highest key).
`guess_key_count` is a best-effort name hint for display only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Standard digital-keyboard sizes, used only to recognize a count in a port name.
_KNOWN_KEY_COUNTS = (88, 76, 61, 49, 37, 32, 25)

_NOTE_ON = 0x90
_NOTE_OFF = 0x80


@dataclass
class MidiMsg:
    """A parsed MIDI message. kind is 'note_on' | 'note_off' | 'other'."""
    kind: str
    note: int
    velocity: int


class _RtMidiBackend:
    """Real backend over rtmidi.MidiIn (imported lazily)."""

    def __init__(self) -> None:
        import rtmidi
        self._midi = rtmidi.MidiIn()

    def get_ports(self) -> list[str]:
        return self._midi.get_ports()

    def open_port(self, index: int) -> None:
        self._midi.open_port(index)

    def get_message(self):
        return self._midi.get_message()

    def close_port(self) -> None:
        self._midi.close_port()


def list_input_ports(backend=None) -> list[str]:
    """Names of available MIDI input ports."""
    backend = backend if backend is not None else _RtMidiBackend()
    return list(backend.get_ports())


def guess_key_count(port_name: str) -> int | None:
    """Best-effort key count parsed from a port name (display hint only).

    Returns the first standard key count appearing as a number in the name, or
    None. The trailing Windows port index is not a key count, so only values in
    the known-size set are accepted."""
    numbers = {int(n) for n in re.findall(r'\d+', port_name)}
    for count in _KNOWN_KEY_COUNTS:
        if count in numbers:
            return count
    return None


def _parse(data: list[int]) -> MidiMsg:
    if not data:
        return MidiMsg('other', 0, 0)
    status = data[0] & 0xF0
    note = data[1] if len(data) > 1 else 0
    velocity = data[2] if len(data) > 2 else 0
    if status == _NOTE_ON:
        # A note_on with velocity 0 is a note_off (running-status convention).
        return MidiMsg('note_on' if velocity > 0 else 'note_off', note, velocity)
    if status == _NOTE_OFF:
        return MidiMsg('note_off', note, velocity)
    return MidiMsg('other', note, velocity)


class MidiInputDevice:
    """An open MIDI input port that yields parsed messages on poll()."""

    def __init__(self, backend=None) -> None:
        self._backend = backend if backend is not None else _RtMidiBackend()
        self._open = False

    def open(self, port_index: int) -> None:
        self._backend.open_port(port_index)
        self._open = True

    def close(self) -> None:
        if self._open:
            self._backend.close_port()
            self._open = False

    def poll(self) -> list[MidiMsg]:
        """Drain all pending messages, parsed and in arrival order."""
        out: list[MidiMsg] = []
        while True:
            item = self._backend.get_message()
            if item is None:
                break
            data, _delta = item
            out.append(_parse(data))
        return out
