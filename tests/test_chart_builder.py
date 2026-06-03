"""
Unit tests for src/game/chart.py — Note, Chart, and ChartBuilder.build().

Tests cover (per ai-working-log/specs/2026-05-04-chart-builder-design.md):
  - Note / Chart dataclass fields
  - MIDI mode: 1:1 lane mapping (lane = note - midi_low)
  - PC mode: linear interpolation onto 8 lanes, edge anchoring, half-up rounding
  - Range validation: notes outside kb_class range raise ValueError (both modes)
  - Sort order: non-decreasing by time_ms; ties keep input order
  - total_duration_ms: longest note end, including non-last hold notes
  - Mode validation and empty-input handling
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.game.chart import Note, Chart, ChartBuilder
from src.midi.classifier import KeyboardClass, classify
from src.midi.parser import NoteEvent


# Keyboard classes used across tests (mirror the classifier table).
KB_25 = KeyboardClass(name='25key', key_count=25, midi_low=48, midi_high=72, lane_count=25)
KB_49 = KeyboardClass(name='49key', key_count=49, midi_low=36, midi_high=84, lane_count=49)


def _ev(note: int, time_ms: float = 0.0, duration_ms: float = 100.0) -> NoteEvent:
    """Helper: build a single NoteEvent with sensible defaults."""
    return NoteEvent(note=note, time_ms=time_ms, duration_ms=duration_ms,
                     channel=0, velocity=80)


class TestNoteDataclass(unittest.TestCase):
    """Note must expose the fields documented in the design spec."""

    def test_fields_exist(self):
        n = Note(lane=3, midi_note=60, time_ms=1500.0, duration_ms=250.0)
        self.assertEqual(n.lane, 3)
        self.assertEqual(n.midi_note, 60)
        self.assertEqual(n.time_ms, 1500.0)
        self.assertEqual(n.duration_ms, 250.0)

    def test_hit_and_missed_default_false(self):
        n = Note(lane=0, midi_note=48, time_ms=0.0, duration_ms=0.0)
        self.assertFalse(n.hit)
        self.assertFalse(n.missed)

    def test_equality(self):
        a = Note(lane=1, midi_note=50, time_ms=10.0, duration_ms=5.0)
        b = Note(lane=1, midi_note=50, time_ms=10.0, duration_ms=5.0)
        self.assertEqual(a, b)


class TestChartDataclass(unittest.TestCase):
    """Chart must expose the fields documented in the design spec."""

    def test_fields_exist(self):
        notes = [Note(lane=0, midi_note=48, time_ms=0.0, duration_ms=0.0)]
        c = Chart(notes=notes, kb_class=KB_25, mode='midi',
                  lane_count=25, total_duration_ms=0.0)
        self.assertEqual(c.notes, notes)
        self.assertEqual(c.kb_class, KB_25)
        self.assertEqual(c.mode, 'midi')
        self.assertEqual(c.lane_count, 25)
        self.assertEqual(c.total_duration_ms, 0.0)


class TestMidiMode(unittest.TestCase):
    """MIDI mode: 1:1 mapping, lane = note - midi_low."""

    def test_lowest_note_maps_to_lane_zero(self):
        chart = ChartBuilder.build([_ev(48)], KB_25, 'midi')
        self.assertEqual(chart.notes[0].lane, 0)

    def test_highest_note_maps_to_top_lane(self):
        chart = ChartBuilder.build([_ev(72)], KB_25, 'midi')
        self.assertEqual(chart.notes[0].lane, 24)

    def test_lane_count_equals_key_count(self):
        chart = ChartBuilder.build([_ev(60)], KB_25, 'midi')
        self.assertEqual(chart.lane_count, KB_25.key_count)

    def test_all_lanes_within_range(self):
        events = [_ev(n, time_ms=float(i)) for i, n in enumerate(range(48, 73))]
        chart = ChartBuilder.build(events, KB_25, 'midi')
        for note in chart.notes:
            with self.subTest(lane=note.lane):
                self.assertGreaterEqual(note.lane, 0)
                self.assertLess(note.lane, chart.lane_count)

    def test_midi_note_preserved(self):
        chart = ChartBuilder.build([_ev(65)], KB_25, 'midi')
        self.assertEqual(chart.notes[0].midi_note, 65)


class TestPcMode(unittest.TestCase):
    """PC mode: linear interpolation onto 8 lanes."""

    def test_lane_count_is_eight(self):
        chart = ChartBuilder.build([_ev(60)], KB_49, 'pc')
        self.assertEqual(chart.lane_count, 8)

    def test_song_min_maps_to_lane_zero(self):
        events = [_ev(60), _ev(71)]
        chart = ChartBuilder.build(events, KB_49, 'pc')
        lanes = {n.midi_note: n.lane for n in chart.notes}
        self.assertEqual(lanes[60], 0)

    def test_song_max_maps_to_lane_seven(self):
        events = [_ev(60), _ev(71)]
        chart = ChartBuilder.build(events, KB_49, 'pc')
        lanes = {n.midi_note: n.lane for n in chart.notes}
        self.assertEqual(lanes[71], 7)

    def test_edge_anchoring_across_ranges(self):
        # song_min always lane 0, song_max always lane 7, for spans 12/24/48
        # (all within the 49key range [36, 84]).
        for low, high in [(60, 72), (48, 72), (36, 84)]:
            events = [_ev(low), _ev(high)]
            chart = ChartBuilder.build(events, KB_49, 'pc')
            lanes = {n.midi_note: n.lane for n in chart.notes}
            with self.subTest(span=high - low):
                self.assertEqual(lanes[low], 0)
                self.assertEqual(lanes[high], 7)

    def test_narrow_two_pitch_song_uses_lanes_0_and_7(self):
        events = [_ev(60), _ev(61)]
        chart = ChartBuilder.build(events, KB_49, 'pc')
        lanes = {n.midi_note: n.lane for n in chart.notes}
        self.assertEqual(lanes[60], 0)
        self.assertEqual(lanes[61], 7)

    def test_single_pitch_song_collapses_to_lane_zero(self):
        events = [_ev(60), _ev(60), _ev(60)]
        chart = ChartBuilder.build(events, KB_49, 'pc')
        for note in chart.notes:
            self.assertEqual(note.lane, 0)

    def test_midrange_pitch_lands_as_expected(self):
        # span [60, 71]: note 65 → int(5/11 * 7 + 0.5) = int(3.68) = 3
        events = [_ev(60), _ev(65), _ev(71)]
        chart = ChartBuilder.build(events, KB_49, 'pc')
        lanes = {n.midi_note: n.lane for n in chart.notes}
        self.assertEqual(lanes[65], 3)

    def test_half_up_rounding_not_bankers(self):
        # span [60, 74]: note 65 → 5/14 * 7 = 2.5 exactly.
        # half-up: int(2.5 + 0.5) = 3. banker's round(2.5) = 2.
        events = [_ev(60), _ev(65), _ev(74)]
        chart = ChartBuilder.build(events, KB_49, 'pc')
        lanes = {n.midi_note: n.lane for n in chart.notes}
        self.assertEqual(lanes[65], 3)


class TestRangeValidation(unittest.TestCase):
    """Notes outside the kb_class range raise ValueError in both modes."""

    def test_midi_mode_note_above_high_raises(self):
        with self.assertRaises(ValueError):
            ChartBuilder.build([_ev(73)], KB_25, 'midi')

    def test_midi_mode_note_below_low_raises(self):
        with self.assertRaises(ValueError):
            ChartBuilder.build([_ev(47)], KB_25, 'midi')

    def test_pc_mode_note_above_high_raises(self):
        with self.assertRaises(ValueError):
            ChartBuilder.build([_ev(73)], KB_25, 'pc')

    def test_pc_mode_note_below_low_raises(self):
        with self.assertRaises(ValueError):
            ChartBuilder.build([_ev(47)], KB_25, 'pc')


class TestSorting(unittest.TestCase):
    """Output is non-decreasing by time_ms; ties keep input order."""

    def test_out_of_order_input_is_sorted(self):
        events = [_ev(60, 3000), _ev(62, 1000), _ev(64, 2000)]
        chart = ChartBuilder.build(events, KB_25, 'midi')
        times = [n.time_ms for n in chart.notes]
        self.assertEqual(times, sorted(times))

    def test_ties_keep_input_order(self):
        # Two events at the same time: input order is 50 then 60.
        events = [_ev(50, 1000), _ev(60, 1000)]
        chart = ChartBuilder.build(events, KB_25, 'midi')
        same_time = [n.midi_note for n in chart.notes if n.time_ms == 1000]
        self.assertEqual(same_time, [50, 60])


class TestTotalDuration(unittest.TestCase):
    """total_duration_ms = max(time_ms + duration_ms)."""

    def test_tap_only_chart(self):
        events = [_ev(60, 1000, 0.0), _ev(62, 5000, 0.0)]
        chart = ChartBuilder.build(events, KB_25, 'midi')
        self.assertEqual(chart.total_duration_ms, 5000.0)

    def test_last_note_has_duration(self):
        events = [_ev(60, 1000, 0.0), _ev(62, 5000, 2000.0)]
        chart = ChartBuilder.build(events, KB_25, 'midi')
        self.assertEqual(chart.total_duration_ms, 7000.0)

    def test_non_last_note_has_longest_end(self):
        # note A: t=4000, dur=3000 → ends 7000 (later than note B's start).
        # note B: t=5000, dur=0    → ends 5000.
        events = [_ev(60, 4000, 3000.0), _ev(62, 5000, 0.0)]
        chart = ChartBuilder.build(events, KB_25, 'midi')
        self.assertEqual(chart.total_duration_ms, 7000.0)

    def test_empty_chart_total_is_zero(self):
        chart = ChartBuilder.build([], KB_25, 'midi')
        self.assertEqual(chart.total_duration_ms, 0.0)


class TestModesAndInputs(unittest.TestCase):
    """Mode validation and empty-input handling."""

    def test_invalid_mode_keyboard_raises(self):
        with self.assertRaises(ValueError):
            ChartBuilder.build([_ev(60)], KB_25, 'keyboard')

    def test_invalid_mode_empty_string_raises(self):
        with self.assertRaises(ValueError):
            ChartBuilder.build([_ev(60)], KB_25, '')

    def test_empty_events_midi_mode(self):
        chart = ChartBuilder.build([], KB_25, 'midi')
        self.assertEqual(chart.notes, [])
        self.assertEqual(chart.lane_count, 25)
        self.assertEqual(chart.total_duration_ms, 0.0)
        self.assertEqual(chart.mode, 'midi')

    def test_empty_events_pc_mode(self):
        chart = ChartBuilder.build([], KB_25, 'pc')
        self.assertEqual(chart.notes, [])
        self.assertEqual(chart.lane_count, 8)
        self.assertEqual(chart.total_duration_ms, 0.0)
        self.assertEqual(chart.mode, 'pc')


class TestIntegrationWithClassifier(unittest.TestCase):
    """ChartBuilder consumes the output of classify() end-to-end."""

    def test_build_from_classified_events(self):
        events = [_ev(48, 0.0), _ev(60, 500.0), _ev(72, 1000.0)]
        kb = classify(events)  # 25key
        chart = ChartBuilder.build(events, kb, 'midi')
        self.assertEqual(chart.kb_class.name, '25key')
        self.assertEqual(len(chart.notes), 3)
        self.assertEqual(chart.notes[0].lane, 0)
        self.assertEqual(chart.notes[-1].lane, 24)


if __name__ == '__main__':
    unittest.main()
