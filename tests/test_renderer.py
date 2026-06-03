"""
Tests for src/ui/renderer.py.

The pure geometry (lane_x, note_center_y) is unit-tested directly. The pygame
drawing is exercised by a headless smoke test using SDL's dummy video/audio
drivers, which proves the renderer and the assembled game loop run without a
display or audio device.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Headless SDL: must be set before pygame is imported anywhere.
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.ui.renderer import lane_x, note_center_y, Renderer
from src.app import make_engine, SIZE
from src.game.chart import Note, Chart
from src.game.engine import GameState
from src.midi.classifier import KeyboardClass

_KB = KeyboardClass(name='25key', key_count=25, midi_low=48, midi_high=72, lane_count=25)


class _ManualClock:
    def __init__(self):
        self.t = 0.0
        self.playing = False

    def play(self): self.playing = True
    def pause(self): self.playing = False
    def resume(self): self.playing = True
    def stop(self): self.playing = False
    def current_ms(self): return self.t
    def is_playing(self): return self.playing


class TestLaneX(unittest.TestCase):

    def test_first_lane_center(self):
        # 8 lanes across 800 px -> lane width 100; lane 0 center at 50.
        self.assertAlmostEqual(lane_x(0, 8, 800), 50.0)

    def test_last_lane_center(self):
        self.assertAlmostEqual(lane_x(7, 8, 800), 750.0)

    def test_lanes_evenly_spaced(self):
        xs = [lane_x(i, 4, 400) for i in range(4)]
        self.assertEqual(xs, [50.0, 150.0, 250.0, 350.0])


class TestNoteCenterY(unittest.TestCase):

    def test_note_at_current_time_sits_on_hit_bar(self):
        # time == current -> y == hit_y.
        self.assertAlmostEqual(note_center_y(1000, 1000, hit_y=600, pixels_per_ms=0.3), 600)

    def test_future_note_is_above_bar(self):
        # 1000 ms in the future at 0.3 px/ms -> 300 px above the bar.
        self.assertAlmostEqual(note_center_y(2000, 1000, hit_y=600, pixels_per_ms=0.3), 300)

    def test_past_note_is_below_bar(self):
        self.assertAlmostEqual(note_center_y(900, 1000, hit_y=600, pixels_per_ms=0.3), 630)


class TestHeadlessPlayableLoop(unittest.TestCase):
    """Drive the fully-assembled game loop (engine + scoring + demo + renderer)
    with no display or audio device, proving it runs and finishes perfectly."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface(SIZE)
        cls.renderer = Renderer(SIZE)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_demo_run_renders_and_finishes_perfect(self):
        notes = [Note(lane=i % 8, midi_note=48 + (i % 8), time_ms=i * 250.0,
                      duration_ms=0.0) for i in range(40)]
        chart = Chart(notes=notes, kb_class=_KB, mode='midi',
                      lane_count=25, total_duration_ms=notes[-1].time_ms)
        clock = _ManualClock()
        engine, scoring = make_engine(chart, clock, demo=True)

        engine.start()
        engine.update(3000)  # countdown -> DEMO
        self._render(chart, engine, scoring)  # exercise a play frame

        seen_states = set()
        for _ in range(100000):
            if engine.is_finished():
                break
            clock.t += 100.0
            engine.update(100.0)
            self._render(chart, engine, scoring)
            seen_states.add(engine.state)

        # Renders the FINISHED results overlay without error.
        self._render(chart, engine, scoring)

        self.assertTrue(engine.is_finished())
        self.assertEqual(scoring.score, 1_000_000)
        self.assertAlmostEqual(scoring.accuracy, 1.0)
        self.assertIn(GameState.DEMO, seen_states)

    def test_demo_without_audio_survives_play(self):
        # Regression: demo mode with no --audio must not crash when the engine
        # calls clock.play() (AudioPlayer with nothing loaded -> 'music not loaded').
        from src.audio.player import AudioPlayer
        chart = Chart(notes=[Note(lane=0, midi_note=48, time_ms=500.0, duration_ms=0.0)],
                      kb_class=_KB, mode='midi', lane_count=25, total_duration_ms=500.0)
        engine, scoring = make_engine(chart, AudioPlayer(), demo=True)
        engine.start()
        for _ in range(4):
            engine.update(1000.0)  # crosses the 3000 ms countdown -> clock.play()
            self._render(chart, engine, scoring)
        self.assertEqual(engine.state, GameState.DEMO)

    def test_renders_countdown_frame(self):
        chart = Chart(notes=[], kb_class=_KB, mode='midi',
                      lane_count=25, total_duration_ms=0.0)
        clock = _ManualClock()
        engine, scoring = make_engine(chart, clock, demo=True)
        engine.start()  # COUNTDOWN
        # Should draw the big "3" without raising.
        self.renderer.render(self.surface, chart, engine.current_ms(), scoring,
                             state=engine.state, countdown=engine.countdown_value(),
                             is_demo=engine.is_demo())

    def _render(self, chart, engine, scoring):
        self.renderer.render(self.surface, chart, engine.current_ms(), scoring,
                             state=engine.state, countdown=engine.countdown_value(),
                             is_demo=engine.is_demo())


if __name__ == '__main__':
    unittest.main()
