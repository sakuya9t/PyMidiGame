"""
Tests for src/input/midi_input.py — MIDI note -> lane adapter.

Maps incoming note_on messages to lane indices for GameEngine.handle_input. The
engine stamps the time itself, so the adapter only carries lanes. Driven by a
fake device serving scripted MidiMsg lists — no hardware.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.input.midi_input import MidiInput
from src.midi.device import MidiMsg


class FakeDevice:
    """Device stub: poll() returns its scripted messages once, then nothing."""

    def __init__(self, msgs):
        self._msgs = list(msgs)

    def poll(self):
        out, self._msgs = self._msgs, []
        return out


def _on(note, vel=100):
    return MidiMsg('note_on', note, vel)


def _off(note):
    return MidiMsg('note_off', note, 0)


class MidiInputTest(unittest.TestCase):

    def test_note_on_maps_to_lane(self):
        # midi_low=36, so note 36 -> lane 0, note 40 -> lane 4.
        mi = MidiInput(FakeDevice([_on(36), _on(40)]), midi_low=36, lane_count=49)
        self.assertEqual(mi.poll(), [0, 4])

    def test_note_below_range_ignored(self):
        mi = MidiInput(FakeDevice([_on(30)]), midi_low=36, lane_count=49)
        self.assertEqual(mi.poll(), [])

    def test_note_above_range_ignored(self):
        # lane_count=25 -> valid lanes 0..24; note 36+25=61 -> lane 25, out of range.
        mi = MidiInput(FakeDevice([_on(61)]), midi_low=36, lane_count=25)
        self.assertEqual(mi.poll(), [])

    def test_note_off_ignored(self):
        mi = MidiInput(FakeDevice([_off(40)]), midi_low=36, lane_count=49)
        self.assertEqual(mi.poll(), [])

    def test_mixed_stream_order_preserved(self):
        mi = MidiInput(
            FakeDevice([_on(36), _off(36), _on(48), MidiMsg('other', 0, 0), _on(37)]),
            midi_low=36, lane_count=49)
        self.assertEqual(mi.poll(), [0, 12, 1])

    def test_empty_poll(self):
        mi = MidiInput(FakeDevice([]), midi_low=36, lane_count=49)
        self.assertEqual(mi.poll(), [])


if __name__ == '__main__':
    unittest.main()
