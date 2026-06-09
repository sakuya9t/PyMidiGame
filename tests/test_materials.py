"""
Tests for src/ui/materials.py — the NeonMaterialKit atlas drawing helpers.

These run headlessly under the SDL dummy driver: they draw onto SRCALPHA
surfaces and inspect pixel alpha, so no real display is required. The atlas
image is expected to be present (as in test_hud); the fallback paths are exercised
by passing unknown region names.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.ui.materials import NeonMaterialKit


class NineSliceTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.kit = NeonMaterialKit()
        if not cls.kit.using_atlas:
            raise unittest.SkipTest('neon atlas image not available')

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _surf(self, w=500, h=300):
        return pygame.Surface((w, h), pygame.SRCALPHA)

    def test_known_panel_returns_true_and_fills_center(self):
        surf = self._surf()
        rect = pygame.Rect(20, 20, 400, 160)
        ok = self.kit.draw_nine_slice(surf, 'blue', 'score_panel', rect)
        self.assertTrue(ok)
        # The interior gets a dark translucent fill (non-transparent).
        self.assertGreater(surf.get_at((rect.centerx, rect.centery)).a, 0)

    def test_corner_pixels_are_drawn(self):
        surf = self._surf()
        rect = pygame.Rect(20, 20, 400, 160)
        self.kit.draw_nine_slice(surf, 'blue', 'score_panel', rect)
        # The panel's top-left corner carries visible frame art.
        self.assertGreater(surf.get_at((rect.left + 3, rect.top + 3)).a, 0)

    def test_unknown_panel_returns_false_and_leaves_surface_clear(self):
        surf = self._surf()
        rect = pygame.Rect(20, 20, 400, 160)
        ok = self.kit.draw_nine_slice(surf, 'blue', 'no_such_panel', rect)
        self.assertFalse(ok)
        self.assertEqual(surf.get_at((rect.centerx, rect.centery)),
                         pygame.Color(0, 0, 0, 0))

    def test_rect_smaller_than_borders_returns_false(self):
        surf = self._surf(100, 100)
        rect = pygame.Rect(0, 0, 10, 10)  # narrower than left + right border
        ok = self.kit.draw_nine_slice(surf, 'blue', 'score_panel', rect)
        self.assertFalse(ok)

    def test_alpha_scales_the_center_fill(self):
        rect = pygame.Rect(20, 20, 400, 160)
        full, faint = self._surf(), self._surf()
        self.kit.draw_nine_slice(full, 'blue', 'score_panel', rect, alpha=255)
        self.kit.draw_nine_slice(faint, 'blue', 'score_panel', rect, alpha=80)
        self.assertGreater(full.get_at((rect.centerx, rect.centery)).a,
                           faint.get_at((rect.centerx, rect.centery)).a)

    def test_explicit_border_overrides_the_registry(self):
        # A caller may pass a measured border directly (spec signature).
        surf = self._surf()
        rect = pygame.Rect(20, 20, 400, 160)
        ok = self.kit.draw_nine_slice(surf, 'red', 'combo_panel', rect,
                                      border=(42, 22, 44, 26))
        self.assertTrue(ok)


if __name__ == '__main__':
    unittest.main()
