"""
Tests for src/ui/results.py — the standalone post-song results screen.

Like the menu and HUD, it draws onto a pygame surface (presented as a GL textured
quad), so it is fully testable headlessly under the SDL dummy driver. These are
smoke tests plus a check that the screen paints an opaque background (it replaces
the playfield rather than overlaying it).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.ui.results import ResultsScreen
from src.ui.menu import SongEntry

SIZE = (1366, 768)


class FakeScoring:
    score = 824100
    max_combo = 73
    accuracy = 0.872
    perfect = 60
    great = 13
    good = 5
    miss = 2

    def rank(self):
        return 'B'


def _entry(title='Greensleeves', artist='Traditional'):
    return SongEntry(name='twinkle', dir='songs/twinkle', midi_path='x.mid',
                     audio_path=None, title=title, artist=artist,
                     key_class='32key', total_duration_ms=30000.0, bpm=100.0)


class ResultsScreenTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = ResultsScreen(SIZE)
        cls.scoring = FakeScoring()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _surface(self):
        return pygame.Surface(SIZE, pygame.SRCALPHA)

    def test_pc_mode_renders_without_error(self):
        surf = self._surface()
        self.screen.render(surf, self.scoring, _entry(), 'pc')

    def test_demo_mode_renders_without_error(self):
        surf = self._surface()
        self.screen.render(surf, self.scoring, _entry(), 'demo')

    def test_empty_artist_renders(self):
        surf = self._surface()
        self.screen.render(surf, self.scoring, _entry(artist=''), 'pc')

    def test_background_is_opaque(self):
        # The results screen replaces the view, so every pixel must be opaque
        # (alpha 255) — no transparent gaps that would show a stale GL frame.
        surf = self._surface()
        self.screen.render(surf, self.scoring, _entry(), 'demo')
        self.assertEqual(surf.get_at((2, 2)).a, 255)
        self.assertEqual(surf.get_at((SIZE[0] - 2, SIZE[1] - 2)).a, 255)


if __name__ == '__main__':
    unittest.main()
