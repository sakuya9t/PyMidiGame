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


def _to_bytes(surface):
    return pygame.image.tostring(surface, 'RGBA')


class GlowTextTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.kit = NeonMaterialKit()
        cls.font = pygame.font.SysFont('consolas,menlo,monospace', 28, bold=True)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _surf(self, w=400, h=200):
        return pygame.Surface((w, h), pygame.SRCALPHA)

    def test_returns_left_top_positioned_rect_by_default(self):
        surf = self._surf()
        rect = self.kit.draw_glow_text(surf, self.font, 'SCORE', (40, 30),
                                       (240, 248, 255), (40, 120, 255))
        self.assertEqual(rect.topleft, (40, 30))

    def test_draws_visible_text_pixels(self):
        surf = self._surf()
        rect = self.kit.draw_glow_text(surf, self.font, 'SCORE', (40, 30),
                                       (240, 248, 255), (40, 120, 255))
        drawn = any(surf.get_at((x, y)).a > 0
                    for x in range(rect.left, rect.right, 2)
                    for y in range(rect.top, rect.bottom, 2))
        self.assertTrue(drawn)

    def test_center_alignment_centers_on_point(self):
        surf = self._surf()
        rect = self.kit.draw_glow_text(surf, self.font, 'X', (200, 100),
                                       (255, 255, 255), (255, 60, 90),
                                       align='center')
        self.assertEqual(rect.center, (200, 100))

    def test_right_alignment_anchors_right_edge(self):
        surf = self._surf()
        rect = self.kit.draw_glow_text(surf, self.font, '0000000', (360, 30),
                                       (255, 255, 255), (40, 120, 255),
                                       align='right')
        self.assertEqual(rect.topright, (360, 30))

    def test_is_deterministic(self):
        a, b = self._surf(), self._surf()
        for s in (a, b):
            self.kit.draw_glow_text(s, self.font, 'COMBO', (40, 30),
                                    (255, 255, 255), (255, 60, 90))
        self.assertEqual(_to_bytes(a), _to_bytes(b))


class OverlayHelperTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.kit = NeonMaterialKit()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_additive_asset_brightens_over_black(self):
        if not self.kit.using_atlas:
            self.skipTest('atlas not available')
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 255))
        ok = self.kit.draw_additive_asset(surf, 'blue', 'impact_spark',
                                          pygame.Rect(45, 45, 110, 102))
        self.assertTrue(ok)
        brightened = any(sum(surf.get_at((x, y))[:3]) > 12
                         for x in range(45, 155, 3)
                         for y in range(45, 147, 3))
        self.assertTrue(brightened)

    def test_additive_asset_unknown_returns_false(self):
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        ok = self.kit.draw_additive_asset(surf, 'blue', 'nope',
                                          pygame.Rect(0, 0, 64, 64))
        self.assertFalse(ok)

    def test_draw_asset_blits_known_region(self):
        if not self.kit.using_atlas:
            self.skipTest('atlas not available')
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        rect = pygame.Rect(20, 20, 120, 120)
        ok = self.kit.draw_asset(surf, 'rank', 'rank_s', rect)
        self.assertTrue(ok)
        drawn = any(surf.get_at((x, y)).a > 0
                    for x in range(rect.left, rect.right, 4)
                    for y in range(rect.top, rect.bottom, 4))
        self.assertTrue(drawn)

    def test_draw_asset_unknown_returns_false(self):
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        ok = self.kit.draw_asset(surf, 'rank', 'rank_z', pygame.Rect(0, 0, 64, 64))
        self.assertFalse(ok)

    def test_noise_tile_is_deterministic_per_seed(self):
        a = self.kit.make_noise_tile((64, 64), seed=7)
        b = self.kit.make_noise_tile((64, 64), seed=7)
        c = self.kit.make_noise_tile((64, 64), seed=8)
        self.assertEqual(a.get_size(), (64, 64))
        self.assertEqual(_to_bytes(a), _to_bytes(b))
        self.assertNotEqual(_to_bytes(a), _to_bytes(c))

    def test_noise_tile_is_sparse_not_blank(self):
        tile = self.kit.make_noise_tile((48, 48), seed=1)
        lit = sum(1 for x in range(48) for y in range(48)
                  if tile.get_at((x, y)).a > 0)
        self.assertGreater(lit, 0)
        self.assertLess(lit, 48 * 48)  # not a solid fill

    def test_scanline_tile_has_line_and_gap_rows(self):
        tile = self.kit.make_scanline_tile((4, 4))
        self.assertEqual(tile.get_size(), (4, 4))
        alphas = [tile.get_at((0, y)).a for y in range(4)]
        self.assertTrue(any(a > 0 for a in alphas))
        self.assertTrue(any(a == 0 for a in alphas))

    def test_load_optional_ui_image_present_and_missing(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        present = os.path.join(root, 'resources', 'ui',
                               'neon_arcade_jacket_placeholder.png')
        self.assertIsNotNone(self.kit.load_optional_ui_image(present))
        self.assertIsNone(self.kit.load_optional_ui_image(
            os.path.join(root, 'resources', 'ui', 'does_not_exist.png')))


if __name__ == '__main__':
    unittest.main()
