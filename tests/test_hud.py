"""
Tests for src/ui/hud.py — the 2D HUD/countdown/results overlay.

The overlay is plain pygame drawing onto an SRCALPHA surface (later uploaded as a
GL texture and composited over the 3D scene), so it is fully testable headlessly
under the SDL dummy driver. These are smoke tests: every screen state draws onto
a transparent surface without error.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.ui.hud import HudOverlay
from src.ui.materials import NeonMaterialKit
from src.game.engine import GameState

SIZE = (960, 720)


class TestMaterialAtlas(unittest.TestCase):
    """The HUD draws its panels/gauges via NeonMaterialKit's atlas assets."""

    def test_neon_texture_atlas_loads(self):
        kit = NeonMaterialKit()
        self.assertTrue(kit.using_atlas)
        self.assertIsNotNone(kit._asset('blue', 'lane', (24, 120)))
        self.assertIsNotNone(kit._asset('red', 'panel', (180, 42)))
        self.assertIsNotNone(kit._asset('blue', 'gauge_filled', (180, 18)))


class FakeScoring:
    score = 123456
    combo = 42
    max_combo = 88
    accuracy = 0.913

    def rank(self):
        return 'A'


class HudOverlayTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.hud = HudOverlay(SIZE)
        cls.scoring = FakeScoring()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _surface(self):
        return pygame.Surface(SIZE, pygame.SRCALPHA)

    def test_playing_hud_draws_without_error(self):
        surf = self._surface()
        self.hud.render(surf, self.scoring, state=GameState.PLAYING,
                        countdown=0, is_demo=False)

    def test_demo_badge_path(self):
        surf = self._surface()
        self.hud.render(surf, self.scoring, state=GameState.DEMO,
                        countdown=0, is_demo=True)

    def test_countdown_draws_big_number(self):
        surf = self._surface()
        self.hud.render(surf, self.scoring, state=GameState.COUNTDOWN,
                        countdown=3, is_demo=False)

    def test_results_overlay_draws(self):
        surf = self._surface()
        self.hud.render(surf, self.scoring, state=GameState.FINISHED,
                        countdown=0, is_demo=False)

    def test_render_clears_to_transparent_first(self):
        # A prior frame's pixels must not bleed through: render starts from
        # fully transparent so only HUD elements remain over the 3D scene.
        surf = self._surface()
        surf.fill((255, 255, 255, 255))
        self.hud.render(surf, self.scoring, state=GameState.PLAYING,
                        countdown=0, is_demo=False)
        # A spot with no HUD element (dead center, mid-board) should be cleared.
        self.assertEqual(surf.get_at((SIZE[0] // 2, SIZE[1] // 2)),
                         pygame.Color(0, 0, 0, 0))


if __name__ == '__main__':
    unittest.main()
