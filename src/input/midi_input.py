"""
src/input/midi_input.py — MIDI note -> lane adapter.

Polls a MidiInputDevice and converts note_on messages into lane indices for
GameEngine.handle_input. In the 1:1 "midi" chart mode, lane = note - midi_low;
notes outside [midi_low, midi_low + lane_count) are ignored, as are note_off
messages (v1 is taps only — hold release is a later refinement).

The engine stamps the hit time from its clock, so the adapter carries only the
lane (not a timestamp).
"""
from __future__ import annotations


class MidiInput:
    """Adapts a MIDI input device to lane presses for the game engine."""

    def __init__(self, device, midi_low: int, lane_count: int) -> None:
        self._device = device
        self._midi_low = midi_low
        self._lane_count = lane_count

    def poll(self) -> list[int]:
        """Lanes pressed since the last poll, in arrival order."""
        lanes: list[int] = []
        for msg in self._device.poll():
            if msg.kind != 'note_on':
                continue
            lane = msg.note - self._midi_low
            if 0 <= lane < self._lane_count:
                lanes.append(lane)
        return lanes

    def close(self) -> None:
        self._device.close()
