"""
Unit tests for src/midi/parser.py — MidiParser and NoteEvent.

Tests follow TDD red-green cycle: each test is written before the
implementation and describes the desired behaviour precisely.

Coverage:
  - NoteEvent dataclass fields
  - MidiParser.parse() with real and synthetic MIDI files
  - Tempo map handling (constant and mid-file tempo changes)
  - note_on / note_off pairing for duration
  - Velocity-0 note_on treated as note_off
  - Type 0, type 1 MIDI file handling
"""
import sys
import os
import unittest
import tempfile

import mido

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.midi.parser import MidiParser, NoteEvent

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'twinkle.mid')


def _make_type0_midi(ticks_per_beat: int, tempo: int, note_events: list) -> mido.MidiFile:
    """Helper: build a type-0 MIDI file in memory and return it."""
    mid = mido.MidiFile(type=0, ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
    for msg in note_events:
        track.append(msg)
    track.append(mido.MetaMessage('end_of_track', time=0))
    return mid


class TestNoteEventDataclass(unittest.TestCase):
    """NoteEvent must be a dataclass with the correct fields and types."""

    def test_note_event_fields(self):
        e = NoteEvent(note=60, time_ms=0.0, duration_ms=500.0, channel=0, velocity=80)
        self.assertEqual(e.note, 60)
        self.assertAlmostEqual(e.time_ms, 0.0)
        self.assertAlmostEqual(e.duration_ms, 500.0)
        self.assertEqual(e.channel, 0)
        self.assertEqual(e.velocity, 80)

    def test_note_event_defaults_absent(self):
        # All fields are required — no defaults.
        with self.assertRaises(TypeError):
            NoteEvent()  # type: ignore

    def test_note_event_equality(self):
        a = NoteEvent(note=60, time_ms=0.0, duration_ms=500.0, channel=0, velocity=80)
        b = NoteEvent(note=60, time_ms=0.0, duration_ms=500.0, channel=0, velocity=80)
        self.assertEqual(a, b)


class TestMidiParserSynthetic(unittest.TestCase):
    """Tests using synthetic MIDI files built from mido primitives.

    Using synthetic files lets us assert exact ms values because we control
    tempo and tick positions precisely.
    """

    def _write_to_tmp(self, mid: mido.MidiFile) -> str:
        f = tempfile.NamedTemporaryFile(suffix='.mid', delete=False)
        f.close()
        mid.save(f.name)
        return f.name

    def test_single_note_at_beat_zero_120bpm(self):
        """At 120 BPM, beat 0 = 0 ms."""
        # 120 BPM → tempo = 500_000 µs/beat
        mid = _make_type0_midi(
            ticks_per_beat=480,
            tempo=500_000,
            note_events=[
                mido.Message('note_on',  channel=0, note=60, velocity=80, time=0),
                mido.Message('note_off', channel=0, note=60, velocity=0,  time=480),
            ],
        )
        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0].time_ms, 0.0, places=1)

    def test_single_note_duration_at_120bpm(self):
        """At 120 BPM, 480 ticks = 1 beat = 500 ms."""
        mid = _make_type0_midi(
            ticks_per_beat=480,
            tempo=500_000,
            note_events=[
                mido.Message('note_on',  channel=0, note=60, velocity=80, time=0),
                mido.Message('note_off', channel=0, note=60, velocity=0,  time=480),
            ],
        )
        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertAlmostEqual(events[0].duration_ms, 500.0, places=1)

    def test_note_starting_at_beat_one_120bpm(self):
        """At 120 BPM, beat 1 start = 500 ms."""
        mid = _make_type0_midi(
            ticks_per_beat=480,
            tempo=500_000,
            note_events=[
                mido.Message('note_on',  channel=0, note=60, velocity=80, time=480),
                mido.Message('note_off', channel=0, note=60, velocity=0,  time=480),
            ],
        )
        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertAlmostEqual(events[0].time_ms, 500.0, places=1)

    def test_velocity_zero_note_on_treated_as_note_off(self):
        """note_on with velocity=0 closes the preceding note_on."""
        mid = _make_type0_midi(
            ticks_per_beat=480,
            tempo=500_000,
            note_events=[
                mido.Message('note_on', channel=0, note=60, velocity=80, time=0),
                mido.Message('note_on', channel=0, note=60, velocity=0,  time=480),
            ],
        )
        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0].duration_ms, 500.0, places=1)

    def test_velocity_zero_notes_stripped(self):
        """Velocity-0 note_on must not appear as a NoteEvent."""
        mid = _make_type0_midi(
            ticks_per_beat=480,
            tempo=500_000,
            note_events=[
                mido.Message('note_on', channel=0, note=60, velocity=80, time=0),
                mido.Message('note_on', channel=0, note=60, velocity=0,  time=480),
            ],
        )
        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertTrue(all(e.velocity > 0 for e in events))

    def test_two_notes_sequential(self):
        """Two sequential notes produce two NoteEvents in time order."""
        mid = _make_type0_midi(
            ticks_per_beat=480,
            tempo=500_000,
            note_events=[
                mido.Message('note_on',  channel=0, note=60, velocity=80, time=0),
                mido.Message('note_off', channel=0, note=60, velocity=0,  time=480),
                mido.Message('note_on',  channel=0, note=62, velocity=80, time=0),
                mido.Message('note_off', channel=0, note=62, velocity=0,  time=480),
            ],
        )
        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertEqual(len(events), 2)
        self.assertLessEqual(events[0].time_ms, events[1].time_ms)

    def test_note_fields_velocity_channel_preserved(self):
        """velocity and channel must be copied into NoteEvent."""
        mid = _make_type0_midi(
            ticks_per_beat=480,
            tempo=500_000,
            note_events=[
                mido.Message('note_on',  channel=3, note=60, velocity=99, time=0),
                mido.Message('note_off', channel=3, note=60, velocity=0,  time=480),
            ],
        )
        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertEqual(events[0].velocity, 99)
        self.assertEqual(events[0].channel, 3)
        self.assertEqual(events[0].note, 60)

    def test_mid_file_tempo_change(self):
        """Tempo change mid-file must be applied to subsequent notes."""
        # First half: 120 BPM (500_000 µs/beat), 480 ticks = 500 ms
        # Tempo change to 60 BPM (1_000_000 µs/beat) at tick 480
        # Second note at tick 960 with tempo 60 BPM: 960-480=480 ticks at 60BPM = 1000 ms after tempo change
        # → absolute time of note 2 = 500 ms (first beat) + 1000 ms (480 ticks at 60 BPM) = 1500 ms
        mid = mido.MidiFile(type=0, ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage('set_tempo', tempo=500_000, time=0))
        track.append(mido.Message('note_on',  channel=0, note=60, velocity=80, time=0))
        track.append(mido.Message('note_off', channel=0, note=60, velocity=0,  time=240))  # at tick 240 = 250ms
        track.append(mido.MetaMessage('set_tempo', tempo=1_000_000, time=240))  # at tick 480 = 500ms
        track.append(mido.Message('note_on',  channel=0, note=62, velocity=80, time=480))  # at tick 960
        track.append(mido.Message('note_off', channel=0, note=62, velocity=0,  time=480))  # at tick 1440
        track.append(mido.MetaMessage('end_of_track', time=0))

        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertEqual(len(events), 2)
        # Note 2 starts at tick 960 → 500ms (first 480 ticks at 120BPM) + 480*1000/480 ms = 500 + 1000 = 1500ms
        self.assertAlmostEqual(events[1].time_ms, 1500.0, places=0)


class TestMidiParserType1(unittest.TestCase):
    """Tests for type 1 (multi-track synchronized) MIDI files."""

    def _write_to_tmp(self, mid: mido.MidiFile) -> str:
        f = tempfile.NamedTemporaryFile(suffix='.mid', delete=False)
        f.close()
        mid.save(f.name)
        return f.name

    def test_type1_merges_tracks(self):
        """Notes from different tracks are merged into a single flat list."""
        mid = mido.MidiFile(type=1, ticks_per_beat=480)

        # Track 0: tempo map
        t0 = mido.MidiTrack()
        mid.tracks.append(t0)
        t0.append(mido.MetaMessage('set_tempo', tempo=500_000, time=0))
        t0.append(mido.MetaMessage('end_of_track', time=0))

        # Track 1: note at tick 0
        t1 = mido.MidiTrack()
        mid.tracks.append(t1)
        t1.append(mido.Message('note_on',  channel=0, note=60, velocity=80, time=0))
        t1.append(mido.Message('note_off', channel=0, note=60, velocity=0,  time=480))
        t1.append(mido.MetaMessage('end_of_track', time=0))

        # Track 2: note at tick 480
        t2 = mido.MidiTrack()
        mid.tracks.append(t2)
        t2.append(mido.Message('note_on',  channel=1, note=62, velocity=70, time=480))
        t2.append(mido.Message('note_off', channel=1, note=62, velocity=0,  time=480))
        t2.append(mido.MetaMessage('end_of_track', time=0))

        path = self._write_to_tmp(mid)
        try:
            events = MidiParser.parse(path)
        finally:
            os.unlink(path)

        self.assertEqual(len(events), 2)
        notes = sorted(events, key=lambda e: e.time_ms)
        self.assertEqual(notes[0].note, 60)
        self.assertAlmostEqual(notes[0].time_ms, 0.0, places=1)
        self.assertEqual(notes[1].note, 62)
        self.assertAlmostEqual(notes[1].time_ms, 500.0, places=1)


class TestMidiParserWithFixture(unittest.TestCase):
    """Integration tests using tests/fixtures/twinkle.mid (Greensleeves)."""

    @classmethod
    def setUpClass(cls):
        cls.events = MidiParser.parse(FIXTURE_PATH)

    def test_returns_list_of_note_events(self):
        self.assertIsInstance(self.events, list)
        for e in self.events:
            self.assertIsInstance(e, NoteEvent)

    def test_nonzero_event_count(self):
        self.assertGreater(len(self.events), 0)

    def test_all_velocities_positive(self):
        for e in self.events:
            with self.subTest(event=e):
                self.assertGreater(e.velocity, 0)

    def test_all_durations_positive(self):
        for e in self.events:
            with self.subTest(event=e):
                self.assertGreater(e.duration_ms, 0)

    def test_all_times_non_negative(self):
        for e in self.events:
            with self.subTest(event=e):
                self.assertGreaterEqual(e.time_ms, 0.0)

    def test_sorted_by_time(self):
        times = [e.time_ms for e in self.events]
        self.assertEqual(times, sorted(times))

    def test_first_note_at_time_zero(self):
        self.assertAlmostEqual(self.events[0].time_ms, 0.0, places=1)

    def test_first_note_duration_matches_expected(self):
        # tempo=631577, ticks_per_beat=256; first note_off at delta=244 ticks
        # ms_per_tick = 631577/256/1000 = 2.4671 ms/tick
        # duration = 244 * 2.4671 ≈ 601.97 ms
        first = next(e for e in self.events if e.time_ms == 0.0)
        self.assertAlmostEqual(first.duration_ms, 601.97, delta=2.0)

    def test_note_range_within_midi_bounds(self):
        for e in self.events:
            with self.subTest(event=e):
                self.assertGreaterEqual(e.note, 0)
                self.assertLessEqual(e.note, 127)

    def test_channel_within_bounds(self):
        for e in self.events:
            with self.subTest(event=e):
                self.assertGreaterEqual(e.channel, 0)
                self.assertLessEqual(e.channel, 15)


if __name__ == '__main__':
    unittest.main()
