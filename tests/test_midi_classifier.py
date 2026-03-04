"""
Unit tests for src/midi/classifier.py — KeyboardClass and classify().

Tests cover:
  - KeyboardClass dataclass fields
  - classify() returning correct size class for each boundary condition
  - classify() for note sets requiring the largest (88key) fallback
  - Lane index formula: lane = note - midi_low
  - Empty note list handling
  - Single-note list
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.midi.classifier import KeyboardClass, classify
from src.midi.parser import NoteEvent


def _make_events(notes: list[int]) -> list[NoteEvent]:
    """Helper: build a minimal NoteEvent list from note numbers."""
    return [
        NoteEvent(note=n, time_ms=float(i) * 100, duration_ms=100.0, channel=0, velocity=80)
        for i, n in enumerate(notes)
    ]


class TestKeyboardClassDataclass(unittest.TestCase):
    """KeyboardClass must expose the fields documented in the design spec."""

    def test_fields_exist(self):
        kc = KeyboardClass(name='25key', key_count=25, midi_low=48, midi_high=72, lane_count=25)
        self.assertEqual(kc.name, '25key')
        self.assertEqual(kc.key_count, 25)
        self.assertEqual(kc.midi_low, 48)
        self.assertEqual(kc.midi_high, 72)
        self.assertEqual(kc.lane_count, 25)

    def test_equality(self):
        a = KeyboardClass(name='49key', key_count=49, midi_low=36, midi_high=84, lane_count=49)
        b = KeyboardClass(name='49key', key_count=49, midi_low=36, midi_high=84, lane_count=49)
        self.assertEqual(a, b)

    def test_no_defaults(self):
        with self.assertRaises(TypeError):
            KeyboardClass()  # type: ignore


class TestClassifyExactBoundaries(unittest.TestCase):
    """Each keyboard class should be selected when notes span its exact range."""

    def test_25key_exact_range(self):
        # 25key: 48–72 (C3–C5)
        events = _make_events([48, 72])
        result = classify(events)
        self.assertEqual(result.name, '25key')

    def test_32key_exact_range(self):
        # 32key: 41–72 (F2–C5)
        events = _make_events([41, 72])
        result = classify(events)
        self.assertEqual(result.name, '32key')

    def test_37key_exact_range(self):
        # 37key: 41–77 (F2–F5)
        events = _make_events([41, 77])
        result = classify(events)
        self.assertEqual(result.name, '37key')

    def test_49key_exact_range(self):
        # 49key: 36–84 (C2–C6)
        events = _make_events([36, 84])
        result = classify(events)
        self.assertEqual(result.name, '49key')

    def test_61key_exact_range(self):
        # 61key: 36–96 (C2–C7)
        events = _make_events([36, 96])
        result = classify(events)
        self.assertEqual(result.name, '61key')

    def test_88key_exact_range(self):
        # 88key: 21–108 (A0–C8)
        events = _make_events([21, 108])
        result = classify(events)
        self.assertEqual(result.name, '88key')


class TestClassifySmallestFit(unittest.TestCase):
    """classify() must return the smallest class that covers the note range."""

    def test_notes_within_25key_range(self):
        # Notes 50–70 fit entirely inside 25key (48–72)
        events = _make_events([50, 70])
        result = classify(events)
        self.assertEqual(result.name, '25key')

    def test_notes_fit_32key_but_not_25key(self):
        # Note 41 is below 25key (48), so 32key (41–72) is the smallest fit
        events = _make_events([41, 60])
        result = classify(events)
        self.assertEqual(result.name, '32key')

    def test_notes_fit_37key_but_not_32key(self):
        # Note 77 is above 32key (72), so 37key (41–77) is the smallest fit
        events = _make_events([41, 77])
        result = classify(events)
        self.assertEqual(result.name, '37key')

    def test_notes_fit_49key_but_not_37key(self):
        # Note 36 is below 37key (41), so 49key (36–84) is the smallest fit
        events = _make_events([36, 70])
        result = classify(events)
        self.assertEqual(result.name, '49key')

    def test_notes_fit_61key_but_not_49key(self):
        # Note 85 is above 49key (84), so 61key (36–96) is the smallest fit
        events = _make_events([36, 85])
        result = classify(events)
        self.assertEqual(result.name, '61key')

    def test_notes_span_beyond_61key_returns_88key(self):
        # Note 20 is below 88key low (21); fallback to 88key
        events = _make_events([20, 100])
        result = classify(events)
        self.assertEqual(result.name, '88key')


class TestClassifyReturnFields(unittest.TestCase):
    """Returned KeyboardClass must have correct range and count fields."""

    def test_25key_fields(self):
        result = classify(_make_events([48, 72]))
        self.assertEqual(result.key_count, 25)
        self.assertEqual(result.midi_low, 48)
        self.assertEqual(result.midi_high, 72)
        self.assertEqual(result.lane_count, 25)

    def test_88key_fields(self):
        result = classify(_make_events([21, 108]))
        self.assertEqual(result.key_count, 88)
        self.assertEqual(result.midi_low, 21)
        self.assertEqual(result.midi_high, 108)
        self.assertEqual(result.lane_count, 88)


class TestLaneIndexFormula(unittest.TestCase):
    """Lane index formula: lane = note - midi_low (per design spec)."""

    def test_lowest_note_maps_to_lane_zero(self):
        result = classify(_make_events([48, 60]))
        self.assertEqual(result.midi_low, 48)
        # lane for note 48 = 48 - 48 = 0
        self.assertEqual(48 - result.midi_low, 0)

    def test_highest_note_lane_is_key_count_minus_one(self):
        result = classify(_make_events([48, 72]))
        # 25key: lanes 0–24; note 72 → lane = 72 - 48 = 24 = key_count - 1
        highest_lane = result.midi_high - result.midi_low
        self.assertEqual(highest_lane, result.key_count - 1)

    def test_all_notes_in_fixture_within_lane_range(self):
        """All notes in any NoteEvent list should produce valid lane indices."""
        notes_list = list(range(48, 73))  # 25key range
        events = _make_events(notes_list)
        result = classify(events)
        for e in events:
            lane = e.note - result.midi_low
            with self.subTest(note=e.note, lane=lane):
                self.assertGreaterEqual(lane, 0)
                self.assertLess(lane, result.key_count)


class TestClassifyEdgeCases(unittest.TestCase):
    """Edge cases: empty list, single note."""

    def test_single_note_returns_smallest_covering_class(self):
        events = _make_events([60])  # C4, fits in 25key (48–72)
        result = classify(events)
        self.assertEqual(result.name, '25key')

    def test_empty_list_returns_25key(self):
        # No notes → default to smallest class
        result = classify([])
        self.assertIsInstance(result, KeyboardClass)
        self.assertEqual(result.name, '25key')


if __name__ == '__main__':
    unittest.main()
