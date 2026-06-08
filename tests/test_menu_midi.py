"""
Tests for the MIDI-related menu behavior in src/ui/menu.py: MIDI mode becomes
selectable only when a device is configured, the keys-mode selector is limited to
the device span, songs that don't fit are not startable in MIDI mode, and 'M'
opens the setup screen.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.ui.menu import (
    SongMenu, SongEntry, StartGame, OpenMidiSetup, MidiConfig,
)

SIZE = (960, 720)
CONFIG = MidiConfig(name='Oxygen Pro 49 1', min_note=36, max_note=84)  # 49-key span


def _entry(name, key_class):
    return SongEntry(name=name, dir=f'songs/{name}', midi_path=f'{name}.mid',
                     audio_path=None, title=name.title(), artist='',
                     key_class=key_class, total_duration_ms=30000.0, bpm=None)


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


SONGS = [_entry('small', '32key'), _entry('huge', '88key')]


class NoDeviceTest(unittest.TestCase):

    def setUp(self):
        self.m = SongMenu(SONGS, SIZE)

    def test_midi_not_selectable_without_device(self):
        self.assertNotIn('midi', self.m.selectable_modes)

    def test_m_opens_setup(self):
        self.assertIsInstance(self.m.handle_event(_key(pygame.K_m)), OpenMidiSetup)

    def test_keys_mode_defaults_auto(self):
        self.assertEqual(self.m.keys_mode, 'auto')


class WithDeviceTest(unittest.TestCase):

    def setUp(self):
        self.m = SongMenu(SONGS, SIZE, midi_config=CONFIG)

    def test_midi_is_selectable(self):
        self.assertIn('midi', self.m.selectable_modes)

    def test_selection_order_matches_display_order(self):
        # Displayed left-to-right as PC, MIDI, Demo; arrows must step that way.
        self.assertEqual(self.m.selectable_modes, ['pc', 'midi', 'demo'])

    def test_right_arrow_moves_to_next_displayed_mode(self):
        self.assertEqual(self.m.input_mode, 'pc')
        self.m.handle_event(_key(pygame.K_RIGHT))
        self.assertEqual(self.m.input_mode, 'midi')
        self.m.handle_event(_key(pygame.K_RIGHT))
        self.assertEqual(self.m.input_mode, 'demo')

    def test_left_arrow_from_pc_wraps_to_demo(self):
        self.m.handle_event(_key(pygame.K_LEFT))
        self.assertEqual(self.m.input_mode, 'demo')

    def test_keys_options_limited_to_span(self):
        self.assertEqual(self.m.keys_options,
                         ['auto', '25key', '32key', '37key', '49key'])

    def test_k_cycles_keys_mode(self):
        self.m.handle_event(_key(pygame.K_k))
        self.assertEqual(self.m.keys_mode, '25key')

    def test_auto_mode_blocks_song_exceeding_span(self):
        # cycle input mode to 'midi'
        self._select_midi()
        # song 'huge' (88key) doesn't fit a 49-key span under AUTO.
        self.m.selected_index = 1
        self.assertFalse(self.m.midi_playable(SONGS[1]))
        self.assertIsNone(self.m.handle_event(_key(pygame.K_RETURN)))

    def test_auto_mode_allows_fitting_song(self):
        self._select_midi()
        self.m.selected_index = 0  # 'small' 32key fits 36..84
        action = self.m.handle_event(_key(pygame.K_RETURN))
        self.assertEqual(action, StartGame(SONGS[0], 'midi', 'auto'))

    def test_fixed_keys_mode_in_startgame(self):
        self._select_midi()
        self.m.handle_event(_key(pygame.K_k))  # keys -> 25key
        self.m.selected_index = 0              # 'small' is 32key...
        # 32key (41-72) does NOT fit inside 25key (48-72): low 41 < 48 -> blocked
        self.assertFalse(self.m.midi_playable(SONGS[0]))

    def test_set_midi_config_enables_midi(self):
        m = SongMenu(SONGS, SIZE)
        self.assertNotIn('midi', m.selectable_modes)
        m.set_midi_config(CONFIG)
        self.assertIn('midi', m.selectable_modes)
        self.assertEqual(m.keys_options, ['auto', '25key', '32key', '37key', '49key'])

    def _select_midi(self):
        # cycle the input mode to 'midi'
        while self.m.input_mode != 'midi':
            self.m.handle_event(_key(pygame.K_RIGHT))


class RenderTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_renders_with_device(self):
        m = SongMenu(SONGS, SIZE, midi_config=CONFIG)
        m.render(pygame.Surface(SIZE, pygame.SRCALPHA))


if __name__ == '__main__':
    unittest.main()
