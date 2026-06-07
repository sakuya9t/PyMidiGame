"""
Tests for src/ui/geometry.py — pure world-space math for the GL renderer.

These functions are camera-agnostic and free of pygame/OpenGL, so they carry the
headless-testable core of the perspective renderer: note depth along the track,
lane X placement across the board, and interval clamping (note culling + the
hold-note "longer than the board" clamp that the legacy renderer left as a FIXME).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui import geometry


class TestNoteZ(unittest.TestCase):

    def test_note_at_current_time_is_at_zero(self):
        self.assertAlmostEqual(geometry.note_z(1000, 1000, 0.01), 0.0)

    def test_future_note_is_positive(self):
        # 1000 ms ahead at 0.01 units/ms -> +10 (far from the hit point).
        self.assertAlmostEqual(geometry.note_z(2000, 1000, 0.01), 10.0)

    def test_past_note_is_negative(self):
        self.assertAlmostEqual(geometry.note_z(500, 1000, 0.01), -5.0)


class TestLaneWorldX(unittest.TestCase):

    def test_first_lane_center(self):
        # 8 lanes across [-3, 3] -> lane width 0.75; lane 0 center at -2.625.
        self.assertAlmostEqual(geometry.lane_world_x(0, 8, -3.0, 3.0), -2.625)

    def test_last_lane_center(self):
        self.assertAlmostEqual(geometry.lane_world_x(7, 8, -3.0, 3.0), 2.625)

    def test_lanes_evenly_spaced(self):
        xs = [geometry.lane_world_x(i, 4, 0.0, 4.0) for i in range(4)]
        self.assertEqual(xs, [0.5, 1.5, 2.5, 3.5])


class TestLaneBoundsWorld(unittest.TestCase):

    def test_lane_edges(self):
        left, right = geometry.lane_bounds_world(0, 8, -3.0, 3.0)
        self.assertAlmostEqual(left, -3.0)
        self.assertAlmostEqual(right, -2.25)

    def test_last_lane_right_edge_is_board_right(self):
        _, right = geometry.lane_bounds_world(7, 8, -3.0, 3.0)
        self.assertAlmostEqual(right, 3.0)


class TestClampInterval(unittest.TestCase):

    def test_interval_fully_inside_is_unchanged(self):
        self.assertEqual(geometry.clamp_interval(1.0, 3.0, 0.0, 5.0), (1.0, 3.0))

    def test_clamps_to_upper_bound(self):
        # a hold longer than the board far edge gets clamped (legacy FIXME).
        self.assertEqual(geometry.clamp_interval(2.0, 9.0, 0.0, 5.0), (2.0, 5.0))

    def test_clamps_to_lower_bound(self):
        self.assertEqual(geometry.clamp_interval(-4.0, 3.0, 0.0, 5.0), (0.0, 3.0))

    def test_no_overlap_returns_none(self):
        self.assertIsNone(geometry.clamp_interval(6.0, 9.0, 0.0, 5.0))

    def test_accepts_reversed_input_order(self):
        # lo/hi may arrive swapped (near/far depending on sign); normalize.
        self.assertEqual(geometry.clamp_interval(3.0, 1.0, 0.0, 5.0), (1.0, 3.0))


if __name__ == '__main__':
    unittest.main()
