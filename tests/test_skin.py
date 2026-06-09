"""
Tests for src/ui/skin.py — the high-level NeonArcadeSkin.

The skin owns the visual treatment of HUD panels (asset choice, glow colors,
text, interior texture). These headless tests draw each panel onto a transparent
surface and assert it produced visible pixels, stays deterministic, and degrades
gracefully when the atlas or the optional bitmaps are unavailable.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.ui.skin import NeonArcadeSkin
from src.ui.materials import NeonMaterialKit


def _to_bytes(surface):
    return pygame.image.tostring(surface, 'RGBA')


def _has_drawn_pixels(surface, rect, step=4):
    return any(surface.get_at((x, y)).a > 0
               for x in range(rect.left, rect.right, step)
               for y in range(rect.top, rect.bottom, step))


class NeonArcadeSkinTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.skin = NeonArcadeSkin()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _surf(self, w=1366, h=768):
        return pygame.Surface((w, h), pygame.SRCALPHA)

    def test_score_panel_draws_visible_pixels(self):
        surf = self._surf()
        rect = pygame.Rect(940, 24, 398, 130)
        self.skin.draw_score_panel(surf, rect, score=123456)
        self.assertTrue(_has_drawn_pixels(surf, rect))

    def test_score_panel_is_deterministic(self):
        a, b = self._surf(), self._surf()
        rect = pygame.Rect(940, 24, 398, 130)
        for s in (a, b):
            self.skin.draw_score_panel(s, rect, score=777)
        self.assertEqual(_to_bytes(a), _to_bytes(b))

    def test_combo_panel_draws_in_both_full_combo_states(self):
        rect = pygame.Rect(998, 176, 340, 126)
        for full in (False, True):
            surf = self._surf()
            self.skin.draw_combo_panel(surf, rect, combo=42, full_combo=full)
            self.assertTrue(_has_drawn_pixels(surf, rect))

    def test_song_panel_title_only(self):
        surf = self._surf()
        rect = pygame.Rect(28, 24, 404, 154)
        self.skin.draw_song_panel(surf, rect, title='Twinkle')
        self.assertTrue(_has_drawn_pixels(surf, rect))

    def test_song_panel_full_metadata_with_jacket(self):
        surf = self._surf()
        rect = pygame.Rect(28, 24, 404, 154)
        jacket = pygame.Surface((120, 120), pygame.SRCALPHA)
        jacket.fill((40, 90, 160, 255))
        self.skin.draw_song_panel(surf, rect, title='Song', artist='Artist',
                                  bpm=128, jacket=jacket)
        self.assertTrue(_has_drawn_pixels(surf, rect))

    def test_gauge_panel_draws_at_min_and_max(self):
        rect = pygame.Rect(28, 194, 356, 88)
        for value in (0.0, 1.0):
            surf = self._surf()
            self.skin.draw_gauge_panel(surf, rect, value=value)
            self.assertTrue(_has_drawn_pixels(surf, rect))

    def test_small_stat_box_draws(self):
        surf = self._surf()
        rect = pygame.Rect(28, 320, 174, 96)
        self.skin.draw_small_stat_box(surf, rect, label='HI-SPEED', value='4.0')
        self.assertTrue(_has_drawn_pixels(surf, rect))

    def test_hit_spark_brightens_over_black(self):
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 255))
        self.skin.draw_hit_spark(surf, (100, 100), family='blue', intensity=1.0)
        brightened = any(sum(surf.get_at((x, y))[:3]) > 12
                         for x in range(40, 160, 3)
                         for y in range(40, 160, 3))
        self.assertTrue(brightened)


class NeonArcadeSkinFallbackTest(unittest.TestCase):
    """The skin must keep drawing when the atlas / optional bitmaps are gone."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_draws_without_optional_bitmaps(self):
        skin = NeonArcadeSkin(jacket_path='/no/jacket.png',
                              panel_tile_path='/no/tile.png')
        surf = pygame.Surface((1366, 768), pygame.SRCALPHA)
        rect = pygame.Rect(28, 24, 404, 154)
        skin.draw_song_panel(surf, rect, title='No Art')
        self.assertTrue(_has_drawn_pixels(surf, rect))

    def test_draws_without_atlas(self):
        kit = NeonMaterialKit(atlas_path='/no/such/atlas.png')
        self.assertFalse(kit.using_atlas)
        skin = NeonArcadeSkin(materials=kit)
        surf = pygame.Surface((1366, 768), pygame.SRCALPHA)
        rect = pygame.Rect(940, 24, 398, 130)
        skin.draw_score_panel(surf, rect, score=999)
        self.assertTrue(_has_drawn_pixels(surf, rect))


if __name__ == '__main__':
    unittest.main()
