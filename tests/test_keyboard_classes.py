"""
Tests for the public keyboard-class helpers in src/midi/classifier.py used to
constrain the menu's keys-mode to a measured device span.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.midi.classifier import (
    KEYBOARD_CLASSES, keyboard_class_by_name, classes_within,
)


class TestKeyboardClassTable(unittest.TestCase):

    def test_six_classes_smallest_first(self):
        self.assertEqual([c.name for c in KEYBOARD_CLASSES],
                         ['25key', '32key', '37key', '49key', '61key', '88key'])


class TestByName(unittest.TestCase):

    def test_known_name(self):
        self.assertEqual(keyboard_class_by_name('49key').key_count, 49)

    def test_unknown_name(self):
        self.assertIsNone(keyboard_class_by_name('99key'))


class TestClassesWithin(unittest.TestCase):

    def test_49key_span_admits_smaller_fitting_classes(self):
        # span 36..84 (a 49-key controller): 25/32/37/49 fit; 61/88 do not.
        names = [c.name for c in classes_within(36, 84)]
        self.assertEqual(names, ['25key', '32key', '37key', '49key'])

    def test_full_piano_span_admits_all(self):
        self.assertEqual(len(classes_within(21, 108)), 6)

    def test_narrow_span_admits_only_25key(self):
        # 25key is 48..72; 32key starts at 41 which is below 48 -> excluded.
        self.assertEqual([c.name for c in classes_within(48, 72)], ['25key'])

    def test_too_narrow_span_admits_none(self):
        self.assertEqual(classes_within(60, 64), [])


if __name__ == '__main__':
    unittest.main()
