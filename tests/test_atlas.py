"""
Tests for src/ui/atlas.py — the shared neon-atlas region table and UV math.

This module is pure data + arithmetic (no pygame, no OpenGL), so it is fully
unit-testable headlessly. It is the single source of truth for atlas sub-rects,
imported by both the 2D NeonMaterialKit and the GL AtlasTexture.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui import atlas


class TestAtlasTable(unittest.TestCase):

    def test_atlas_size_matches_image(self):
        self.assertEqual(atlas.ATLAS_SIZE, (1254, 1254))

    def test_has_three_color_families(self):
        self.assertEqual(set(atlas.ATLAS_RECTS), {'blue', 'white', 'red'})

    def test_blue_lane_rect_present(self):
        self.assertEqual(atlas.ATLAS_RECTS['blue']['lane'], (34, 72, 82, 498))


class TestUV(unittest.TestCase):

    def test_unknown_family_returns_none(self):
        self.assertIsNone(atlas.uv('green', 'lane'))

    def test_unknown_name_returns_none(self):
        self.assertIsNone(atlas.uv('blue', 'nope'))

    def test_u_coordinates_span_rect_width(self):
        # blue/lane = (34, 72, 82, 498); W = 1254
        u0, _, u1, _ = atlas.uv('blue', 'lane')
        self.assertAlmostEqual(u0, 34 / 1254)
        self.assertAlmostEqual(u1, (34 + 82) / 1254)

    def test_v_is_flipped_for_gl_bottom_left_origin(self):
        # blue/lane top pixel y=72, bottom pixel y=570; H = 1254.
        # v0 (top edge) = 1 - 72/1254 ; v1 (bottom edge) = 1 - 570/1254
        _, v0, _, v1 = atlas.uv('blue', 'lane')
        self.assertAlmostEqual(v0, 1 - 72 / 1254)
        self.assertAlmostEqual(v1, 1 - 570 / 1254)
        # Top edge sits higher in GL v-space than the bottom edge.
        self.assertGreater(v0, v1)

    def test_all_coordinates_within_unit_range(self):
        for family, names in atlas.ATLAS_RECTS.items():
            for name in names:
                u0, v0, u1, v1 = atlas.uv(family, name)
                for c in (u0, v0, u1, v1):
                    self.assertGreaterEqual(c, 0.0)
                    self.assertLessEqual(c, 1.0)


class TestNeonArcadeSkinRegions(unittest.TestCase):
    """Phase 5 registers the HUD frames / FX measured in the skin spec."""

    def test_score_panel_registered(self):
        self.assertEqual(atlas.ATLAS_RECTS['blue']['score_panel'],
                         (740, 67, 484, 101))

    def test_combo_panel_registered(self):
        self.assertEqual(atlas.ATLAS_RECTS['red']['combo_panel'],
                         (739, 214, 483, 90))

    def test_first_pass_blue_panels_present(self):
        for name in ('song_info_panel', 'gauge_panel', 'small_stat_box',
                     'generic_wide_panel', 'gauge_overlay_glow'):
            self.assertIn(name, atlas.ATLAS_RECTS['blue'])

    def test_impact_spark_in_every_family(self):
        for family in ('blue', 'white', 'red'):
            self.assertIn('impact_spark', atlas.ATLAS_RECTS[family])

    def test_glint_tiny_in_every_family(self):
        for family in ('blue', 'white', 'red'):
            self.assertIn('glint_tiny', atlas.ATLAS_RECTS[family])

    def test_still_only_three_color_families(self):
        # Rank badges (a 4th family) are deferred to the results-polish pass.
        self.assertEqual(set(atlas.ATLAS_RECTS), {'blue', 'white', 'red'})


class TestNineSliceBorders(unittest.TestCase):
    """Measured nine-slice borders, ordered (left, top, right, bottom)."""

    def test_score_panel_border(self):
        self.assertEqual(atlas.nine_slice('blue', 'score_panel'),
                         (42, 24, 50, 26))

    def test_combo_panel_border(self):
        self.assertEqual(atlas.nine_slice('red', 'combo_panel'),
                         (42, 22, 44, 26))

    def test_song_info_panel_border(self):
        self.assertEqual(atlas.nine_slice('blue', 'song_info_panel'),
                         (92, 18, 30, 34))

    def test_unknown_nine_slice_returns_none(self):
        self.assertIsNone(atlas.nine_slice('blue', 'lane'))
        self.assertIsNone(atlas.nine_slice('green', 'score_panel'))

    def test_every_nine_slice_target_is_a_registered_rect(self):
        for family, names in atlas.NINE_SLICE_BORDERS.items():
            for name in names:
                self.assertIn(name, atlas.ATLAS_RECTS.get(family, {}))


if __name__ == '__main__':
    unittest.main()
