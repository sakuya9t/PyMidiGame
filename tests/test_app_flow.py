"""
Tests for the App state machine in src/app.py — the MENU -> PLAYING -> RESULTS
loop that turns the song menu, game engine, and renderer into one navigable game.

The flow is driven headlessly: SDL dummy drivers, and a manual-clock audio
factory injected so the test can fast-forward a demo run to FINISHED without a
real audio device or wall-clock sleeps.
"""
import sys
import os
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.app import App, AppScreen, SIZE
from src.ui.menu import StartGame
from src.game.engine import GameState

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
TWINKLE = os.path.join(FIXTURES, 'twinkle.mid')


class ManualClock:
    """Controllable Clock: time only moves when the test advances it."""
    def __init__(self):
        self.t = 0.0
        self.playing = False

    def play(self): self.playing = True
    def pause(self): self.playing = False
    def resume(self): self.playing = True
    def stop(self): self.playing = False
    def current_ms(self): return self.t
    def is_playing(self): return self.playing


class ClockFactory:
    """Audio factory stand-in: hands out manual clocks and keeps the latest."""
    def __init__(self):
        self.last = None

    def __call__(self, entry, chart):
        self.last = ManualClock()
        return self.last


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


class AppFlowTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='midimania-flow-')
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        d = os.path.join(self.root, 'twinkle')
        os.makedirs(d)
        shutil.copy(TWINKLE, os.path.join(d, 'chart.mid'))
        self.clocks = ClockFactory()
        self.app = App(self.root, SIZE, surface=pygame.Surface(SIZE),
                       audio_factory=self.clocks)

    # --- screen state ------------------------------------------------------

    def test_starts_on_menu(self):
        self.assertEqual(self.app.screen, AppScreen.MENU)

    def test_menu_lists_seeded_song(self):
        self.assertEqual([s.name for s in self.app.songs], ['twinkle'])

    # --- transitions -------------------------------------------------------

    def test_start_game_pc_is_not_demo(self):
        self.app.start_game(self.app.songs[0], 'pc')
        self.assertEqual(self.app.screen, AppScreen.PLAYING)
        self.assertFalse(self.app.engine.is_demo())
        self.assertEqual(self.app.chart.mode, 'pc')

    def test_start_game_demo_uses_midi_mode(self):
        self.app.start_game(self.app.songs[0], 'demo')
        self.assertEqual(self.app.chart.mode, 'midi')
        self.app.update(3000)  # cross countdown -> DEMO (is_demo is state-based)
        self.assertTrue(self.app.engine.is_demo())

    def test_menu_enter_starts_game(self):
        self.app.handle_event(_key(pygame.K_RIGHT))   # mode -> demo
        self.app.handle_event(_key(pygame.K_RETURN))
        self.assertEqual(self.app.screen, AppScreen.PLAYING)
        self.app.update(3000)  # cross countdown -> DEMO
        self.assertTrue(self.app.engine.is_demo())

    def test_playing_escape_returns_to_menu(self):
        self.app.start_game(self.app.songs[0], 'pc')
        self.app.handle_event(_key(pygame.K_ESCAPE))
        self.assertEqual(self.app.screen, AppScreen.MENU)

    def test_demo_run_finishes_to_results_perfect(self):
        self.app.start_game(self.app.songs[0], 'demo')
        self.app.update(3000)  # cross the countdown -> DEMO, clock.play()
        clock = self.clocks.last
        for _ in range(4000):
            if self.app.screen is AppScreen.RESULTS:
                break
            clock.t += 100.0
            self.app.update(100.0)
        self.assertEqual(self.app.screen, AppScreen.RESULTS)
        self.assertEqual(self.app.scoring.score, 1_000_000)
        self.assertAlmostEqual(self.app.scoring.accuracy, 1.0)

    def test_results_enter_returns_to_menu(self):
        self.app.start_game(self.app.songs[0], 'demo')
        self.app._screen = AppScreen.RESULTS  # jump to results for this unit
        self.app.handle_event(_key(pygame.K_RETURN))
        self.assertEqual(self.app.screen, AppScreen.MENU)

    def test_results_retry_replays_same_song(self):
        self.app.start_game(self.app.songs[0], 'demo')
        first = self.clocks.last
        self.app._screen = AppScreen.RESULTS
        self.app.handle_event(_key(pygame.K_r))
        self.assertEqual(self.app.screen, AppScreen.PLAYING)
        self.assertIsNot(self.clocks.last, first)  # fresh clock for the retry
        self.app.update(3000)  # cross countdown -> DEMO
        self.assertTrue(self.app.engine.is_demo())

    # --- loop --------------------------------------------------------------

    def test_quit_event_stops_step(self):
        running = self.app.step(16.0, [pygame.event.Event(pygame.QUIT)])
        self.assertFalse(running)

    def test_step_renders_each_screen_without_error(self):
        self.assertTrue(self.app.step(16.0, []))                       # MENU
        self.app.start_game(self.app.songs[0], 'demo')
        self.assertTrue(self.app.step(3000.0, []))                     # PLAYING
        self.app._screen = AppScreen.RESULTS
        self.assertTrue(self.app.step(16.0, []))                       # RESULTS


if __name__ == '__main__':
    unittest.main()
