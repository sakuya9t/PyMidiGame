"""
Tests for src/ui/midi_setup.py — the MIDI device select + calibration screen.

The screen is a state machine: SELECT_DEVICE -> CALIBRATE_LOW -> CALIBRATE_HIGH
-> DONE. Pressing the lowest then highest key both confirms the connection and
measures the playable span. Logic is driven by synthetic key events and MidiMsgs
(no hardware); rendering is a headless smoke test.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.ui.midi_setup import (
    MidiSetup, SetupStep, OpenDevice, MidiConfigured, CancelSetup,
)
from src.midi.device import MidiMsg

PORTS = ['Focusrite USB MIDI 0', 'Oxygen Pro 49 1']
SIZE = (1366, 768)


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def _on(note):
    return MidiMsg('note_on', note, 100)


class SelectDeviceTest(unittest.TestCase):

    def setUp(self):
        self.s = MidiSetup(PORTS, SIZE)

    def test_starts_on_select_device(self):
        self.assertEqual(self.s.step, SetupStep.SELECT_DEVICE)
        self.assertEqual(self.s.selected, 0)

    def test_down_moves_selection_clamped(self):
        self.s.handle_key(_key(pygame.K_DOWN))
        self.assertEqual(self.s.selected, 1)
        self.s.handle_key(_key(pygame.K_DOWN))  # clamp at last
        self.assertEqual(self.s.selected, 1)

    def test_up_clamped_at_zero(self):
        self.s.handle_key(_key(pygame.K_UP))
        self.assertEqual(self.s.selected, 0)

    def test_enter_opens_device_and_starts_calibration(self):
        self.s.handle_key(_key(pygame.K_DOWN))  # select port 1
        action = self.s.handle_key(_key(pygame.K_RETURN))
        self.assertEqual(action, OpenDevice(1))
        self.assertEqual(self.s.step, SetupStep.CALIBRATE_LOW)

    def test_escape_cancels(self):
        self.assertIs(self.s.handle_key(_key(pygame.K_ESCAPE)), CancelSetup)


class CalibrationTest(unittest.TestCase):

    def setUp(self):
        self.s = MidiSetup(PORTS, SIZE)
        self.s.handle_key(_key(pygame.K_DOWN))     # select 'Oxygen Pro 49 1'
        self.s.handle_key(_key(pygame.K_RETURN))   # -> CALIBRATE_LOW

    def test_lowest_then_highest_captures_span(self):
        self.s.handle_midi([_on(36)])
        self.assertEqual(self.s.step, SetupStep.CALIBRATE_HIGH)
        self.s.handle_midi([_on(84)])
        self.assertEqual(self.s.step, SetupStep.DONE)
        self.assertEqual((self.s.min_note, self.s.max_note), (36, 84))
        self.assertEqual(self.s.key_count, 49)

    def test_reversed_presses_are_normalized(self):
        self.s.handle_midi([_on(84)])   # "low" press higher
        self.s.handle_midi([_on(36)])   # "high" press lower
        self.assertEqual((self.s.min_note, self.s.max_note), (36, 84))

    def test_equal_high_press_ignored(self):
        self.s.handle_midi([_on(60)])
        self.s.handle_midi([_on(60)])   # same key can't define a span
        self.assertEqual(self.s.step, SetupStep.CALIBRATE_HIGH)

    def test_note_off_does_not_advance(self):
        self.s.handle_midi([MidiMsg('note_off', 36, 0)])
        self.assertEqual(self.s.step, SetupStep.CALIBRATE_LOW)

    def test_last_note_echoed_for_connection_feedback(self):
        self.s.handle_midi([_on(48)])
        self.assertEqual(self.s.last_note, 48)

    def test_done_enter_emits_config(self):
        self.s.handle_midi([_on(36)])
        self.s.handle_midi([_on(84)])
        action = self.s.handle_key(_key(pygame.K_RETURN))
        self.assertEqual(action, MidiConfigured(1, 'Oxygen Pro 49 1', 36, 84))

    def test_done_redo_restarts_calibration(self):
        self.s.handle_midi([_on(36)])
        self.s.handle_midi([_on(84)])
        self.s.handle_key(_key(pygame.K_r))
        self.assertEqual(self.s.step, SetupStep.CALIBRATE_LOW)
        self.assertIsNone(self.s.min_note)


class EmptyAndRenderTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_enter_with_no_ports_does_nothing(self):
        s = MidiSetup([], SIZE)
        self.assertIsNone(s.handle_key(_key(pygame.K_RETURN)))
        self.assertEqual(s.step, SetupStep.SELECT_DEVICE)

    def test_renders_every_step(self):
        s = MidiSetup(PORTS, SIZE)
        surf = pygame.Surface(SIZE, pygame.SRCALPHA)
        s.render(surf)                                   # SELECT_DEVICE
        s.handle_key(_key(pygame.K_RETURN))
        s.render(surf)                                   # CALIBRATE_LOW
        s.handle_midi([_on(36)]); s.render(surf)         # CALIBRATE_HIGH
        s.handle_midi([_on(84)]); s.render(surf)         # DONE


if __name__ == '__main__':
    unittest.main()
