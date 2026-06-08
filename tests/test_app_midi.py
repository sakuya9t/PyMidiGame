"""
App-level tests for the MIDI flow: opening the setup screen, calibrating a
device (which configures it and enables MIDI mode), and routing a polled note_on
into the engine during a MIDI run.

Driven headlessly with a fake device + ports provider — no hardware.
"""
import sys
import os
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.app import App, AppScreen, SIZE
from src.ui.menu import MidiConfig
from src.midi.device import MidiMsg

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
TWINKLE = os.path.join(FIXTURES, 'twinkle.mid')
PORTS = ['Fake Keyboard 49']


class ManualClock:
    def __init__(self):
        self.t = 0.0
        self.playing = False

    def play(self): self.playing = True
    def pause(self): self.playing = False
    def resume(self): self.playing = True
    def stop(self): self.playing = False
    def current_ms(self): return self.t
    def is_playing(self): return self.playing


class ClockFactory:
    def __init__(self):
        self.last = None

    def __call__(self, entry, chart):
        self.last = ManualClock()
        return self.last


class FakeMidiDevice:
    def __init__(self):
        self.pending = []
        self.closed = False

    def feed(self, *msgs):
        self.pending.extend(msgs)

    def poll(self):
        out, self.pending = self.pending, []
        return out

    def close(self):
        self.closed = True


class DeviceFactory:
    """Creates a fresh FakeMidiDevice per open; records opened indices."""
    def __init__(self):
        self.opened = []

    def __call__(self, index):
        self.opened.append(index)
        return FakeMidiDevice()


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def _on(note):
    return MidiMsg('note_on', note, 100)


class AppMidiTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='midimania-midi-')
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        d = os.path.join(self.root, 'twinkle')
        os.makedirs(d)
        shutil.copy(TWINKLE, os.path.join(d, 'chart.mid'))
        self.clocks = ClockFactory()
        self.devices = DeviceFactory()
        self.app = App(self.root, SIZE, surface=pygame.Surface(SIZE),
                       audio_factory=self.clocks,
                       ports_provider=lambda: list(PORTS),
                       midi_device_factory=self.devices)

    # --- setup screen ------------------------------------------------------

    def test_m_opens_setup_screen(self):
        self.app.handle_event(_key(pygame.K_m))
        self.assertEqual(self.app.screen, AppScreen.MIDI_SETUP)

    def test_calibration_configures_device_and_enables_midi(self):
        self.app.handle_event(_key(pygame.K_m))            # -> MIDI_SETUP
        self.app.handle_event(_key(pygame.K_RETURN))       # select device -> open
        dev = self.app._midi_device
        self.assertIsNotNone(dev)

        dev.feed(_on(36)); self.app.update(0)              # lowest key
        dev.feed(_on(84)); self.app.update(0)              # highest key
        self.app.handle_event(_key(pygame.K_RETURN))       # save

        self.assertEqual(self.app.screen, AppScreen.MENU)
        self.assertEqual(self.app._midi_config,
                         MidiConfig('Fake Keyboard 49', 36, 84))
        self.assertIn('midi', self.app._menu.selectable_modes)
        self.assertTrue(dev.closed)  # setup device released

    def test_cancel_setup_returns_to_menu(self):
        self.app.handle_event(_key(pygame.K_m))
        self.app.handle_event(_key(pygame.K_ESCAPE))
        self.assertEqual(self.app.screen, AppScreen.MENU)
        self.assertIsNone(self.app._midi_config)

    # --- MIDI play ---------------------------------------------------------

    def test_midi_run_routes_press_into_scoring(self):
        # Pretend a device was calibrated.
        self.app._midi_port_index = 0
        self.app._midi_config = MidiConfig('Fake Keyboard 49', 36, 84)

        self.app.start_game(self.app.songs[0], 'midi', '49key')
        self.assertEqual(self.app.screen, AppScreen.PLAYING)
        self.assertFalse(self.app.engine.is_demo())   # real play, not auto

        dev = self.app._midi_device
        chart = self.app.chart
        note = chart.notes[0]
        clock = self.clocks.last

        self.app.update(3000)          # cross countdown -> PLAYING
        clock.t = note.time_ms         # align the clock to the note
        dev.feed(_on(note.lane + chart.kb_class.midi_low))
        self.app.update(1)             # poll -> handle_input at note time

        self.assertEqual(self.app.scoring.perfect, 1)

    def test_leaving_midi_run_closes_device(self):
        self.app._midi_port_index = 0
        self.app._midi_config = MidiConfig('Fake Keyboard 49', 36, 84)
        self.app.start_game(self.app.songs[0], 'midi', '49key')
        dev = self.app._midi_device
        self.app.handle_event(_key(pygame.K_ESCAPE))   # back to menu
        self.assertEqual(self.app.screen, AppScreen.MENU)
        self.assertTrue(dev.closed)
        self.assertIsNone(self.app._midi_input)


if __name__ == '__main__':
    unittest.main()
