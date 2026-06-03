"""
Unit tests for src/input/signal.py — InputSignal dataclass.

InputSignal is the shared currency between input/demo producers and the game
engine: "hit lane L at chart-clock time T".
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.input.signal import InputSignal


class TestInputSignal(unittest.TestCase):

    def test_fields_exist(self):
        sig = InputSignal(lane=3, time_ms=1500.0)
        self.assertEqual(sig.lane, 3)
        self.assertEqual(sig.time_ms, 1500.0)

    def test_equality(self):
        a = InputSignal(lane=2, time_ms=10.0)
        b = InputSignal(lane=2, time_ms=10.0)
        self.assertEqual(a, b)

    def test_inequality(self):
        a = InputSignal(lane=2, time_ms=10.0)
        b = InputSignal(lane=2, time_ms=11.0)
        self.assertNotEqual(a, b)

    def test_required_args(self):
        with self.assertRaises(TypeError):
            InputSignal()  # type: ignore


if __name__ == '__main__':
    unittest.main()
