"""
Tests for piano-accurate lane coloring in src/ui/renderer.py.

In MIDI (1:1) mode each lane is a specific key: white keys render white, black
keys (C#/D#/F#/G#/A#) render blue, and there is no red lane. These helpers are
pure (no GL), so they test headlessly.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.renderer import is_black_key, lane_family, lane_overlay_alpha


class TestIsBlackKey(unittest.TestCase):

    def test_naturals_are_white(self):
        for note in (60, 62, 64, 65, 67, 69, 71):  # C D E F G A B (octave 4)
            self.assertFalse(is_black_key(note))

    def test_accidentals_are_black(self):
        for note in (61, 63, 66, 68, 70):  # C# D# F# G# A#
            self.assertTrue(is_black_key(note))

    def test_octave_independent(self):
        self.assertEqual(is_black_key(36), is_black_key(48))  # both C, white


class TestLaneFamily(unittest.TestCase):

    def test_midi_mode_maps_keys_to_white_and_blue(self):
        # midi_low=36 (C2): lane 0=C white, 1=C# blue, 2=D white, 3=D# blue,
        # 4=E white, 5=F white, 6=F# blue.
        expected = ['white', 'blue', 'white', 'blue', 'white', 'white', 'blue']
        got = [lane_family(lane, 'midi', 36, 49) for lane in range(7)]
        self.assertEqual(got, expected)

    def test_midi_mode_never_returns_red(self):
        families = {lane_family(lane, 'midi', 36, 49) for lane in range(49)}
        self.assertEqual(families, {'white', 'blue'})

    def test_pc_mode_center_lane_is_red(self):
        # PC mode has 9 lanes; the center (index 4, the space bar) is red.
        self.assertEqual(lane_family(4, 'pc', 0, 9), 'red')

    def test_pc_mode_non_center_lanes_alternate_white_blue(self):
        families = [lane_family(lane, 'pc', 0, 9) for lane in range(9)
                    if lane != 4]
        self.assertEqual(set(families), {'white', 'blue'})


class TestLaneOverlayAlpha(unittest.TestCase):
    """The lane atlas overlay is a very faint detail wash over dark glass lanes,
    and fades further on thin 49-key layouts so texture density stays readable."""

    def test_few_wide_lanes_get_only_a_faint_overlay(self):
        self.assertLessEqual(lane_overlay_alpha(9), 0.06)

    def test_many_thin_lanes_get_a_faint_overlay(self):
        self.assertLessEqual(lane_overlay_alpha(49), 0.02)

    def test_alpha_never_increases_with_lane_count(self):
        counts = [4, 9, 12, 13, 25, 26, 49, 61, 88]
        alphas = [lane_overlay_alpha(n) for n in counts]
        for a, b in zip(alphas, alphas[1:]):
            self.assertGreaterEqual(a, b)

    def test_alpha_stays_a_subtle_wash(self):
        for n in (1, 9, 25, 49, 88):
            self.assertGreater(lane_overlay_alpha(n), 0.0)
            self.assertLessEqual(lane_overlay_alpha(n), 0.06)


if __name__ == '__main__':
    unittest.main()
