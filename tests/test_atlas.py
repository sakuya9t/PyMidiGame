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


if __name__ == '__main__':
    unittest.main()
