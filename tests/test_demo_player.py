"""
Unit tests for src/game/demo.py — DemoPlayer — plus a headless end-to-end test
that drives the full game core (parser -> classify -> chart -> engine + scoring
+ demo) and asserts a perfect auto-played run.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.game.demo import DemoPlayer
from src.game.chart import Note, Chart
from src.game.engine import GameEngine
from src.game.scoring import ScoringEngine
from src.midi.classifier import KeyboardClass, classify
from src.midi.parser import MidiParser
from src.game.chart import ChartBuilder
from src.input.signal import InputSignal

KB = KeyboardClass(name='25key', key_count=25, midi_low=48, midi_high=72, lane_count=25)
FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'twinkle.mid')


def _n(lane: int, time_ms: float, dur: float = 0.0) -> Note:
    return Note(lane=lane, midi_note=48 + lane, time_ms=time_ms, duration_ms=dur)


def _chart(notes: list[Note]) -> Chart:
    total = max((n.time_ms + n.duration_ms for n in notes), default=0.0)
    return Chart(notes=notes, kb_class=KB, mode='midi',
                 lane_count=25, total_duration_ms=total)


class ManualClock:
    """A clock whose time the test advances by hand."""

    def __init__(self):
        self.t = 0.0
        self.playing = False

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

    def resume(self):
        self.playing = True

    def stop(self):
        self.playing = False

    def current_ms(self):
        return self.t

    def is_playing(self):
        return self.playing


class TestDemoPlayer(unittest.TestCase):

    def test_pops_due_notes_as_signals(self):
        demo = DemoPlayer(_chart([_n(0, 100), _n(1, 200)]))
        sigs = demo.tick(150)
        self.assertEqual(sigs, [InputSignal(lane=0, time_ms=100)])

    def test_signal_carries_note_lane_and_time(self):
        demo = DemoPlayer(_chart([_n(3, 500)]))
        sigs = demo.tick(500)
        self.assertEqual(sigs[0].lane, 3)
        self.assertEqual(sigs[0].time_ms, 500)

    def test_each_note_emitted_once(self):
        demo = DemoPlayer(_chart([_n(0, 100)]))
        self.assertEqual(len(demo.tick(100)), 1)
        self.assertEqual(demo.tick(100), [])  # already popped

    def test_not_yet_due_notes_withheld(self):
        demo = DemoPlayer(_chart([_n(0, 100), _n(1, 9999)]))
        sigs = demo.tick(100)
        self.assertEqual([s.lane for s in sigs], [0])

    def test_hold_note_emits_single_press(self):
        # Release signalling is deferred (InputSignal has no release type).
        demo = DemoPlayer(_chart([_n(0, 100, dur=400)]))
        sigs = demo.tick(100)
        self.assertEqual(sigs, [InputSignal(lane=0, time_ms=100)])

    def test_signals_sorted_by_time(self):
        demo = DemoPlayer(_chart([_n(0, 300), _n(1, 100), _n(2, 200)]))
        sigs = demo.tick(1000)
        self.assertEqual([s.time_ms for s in sigs], [100, 200, 300])


class TestDemoEndToEnd(unittest.TestCase):
    """The full game core, headless, auto-played to a perfect score."""

    def _run_demo(self, chart):
        clock = ManualClock()
        scoring = ScoringEngine()
        engine = GameEngine(clock, scoring, countdown_ms=3000, end_padding_ms=2000)
        engine.load(chart, demo_source=DemoPlayer(chart))
        engine.start()
        engine.update(3000)  # cross countdown -> DEMO (clock.play)
        # Drive frames, advancing the clock until the engine reports finished.
        for _ in range(100000):
            if engine.is_finished():
                break
            clock.t += 100.0
            engine.update(100.0)
        return scoring

    def test_synthetic_chart_perfect_run(self):
        chart = _chart([_n(i % 8, i * 250.0) for i in range(40)])
        scoring = self._run_demo(chart)
        self.assertEqual(scoring.score, 1_000_000)
        self.assertAlmostEqual(scoring.accuracy, 1.0)
        self.assertEqual(scoring.rank(), 'S')

    def test_real_fixture_perfect_run(self):
        events = MidiParser.parse(FIXTURE)
        kb = classify(events)
        chart = ChartBuilder.build(events, kb, 'midi')
        scoring = self._run_demo(chart)
        self.assertEqual(scoring.score, 1_000_000)
        self.assertAlmostEqual(scoring.accuracy, 1.0)
        self.assertEqual(scoring.rank(), 'S')


if __name__ == '__main__':
    unittest.main()
