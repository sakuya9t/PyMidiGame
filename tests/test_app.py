"""
Tests for src/app.py audio source selection.

By default the MIDI file itself is the music (pygame.mixer can synthesize a
.mid); --audio overrides it with a produced track. A load failure (e.g. a
platform with no MIDI backend) degrades to a silent run rather than crashing.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from src.app import make_audio


class FakeBackend:
    def __init__(self, raise_on_load=False):
        self.calls = []
        self._raise = raise_on_load

    def load(self, path):
        if self._raise:
            raise RuntimeError('no MIDI backend')
        self.calls.append(('load', path))

    def play(self): self.calls.append(('play',))
    def pause(self): self.calls.append(('pause',))
    def unpause(self): self.calls.append(('unpause',))
    def stop(self): self.calls.append(('stop',))


class TestMakeAudio(unittest.TestCase):

    def test_defaults_to_the_midi_file(self):
        fb = FakeBackend()
        make_audio('song.mid', None, backend=fb)
        self.assertIn(('load', 'song.mid'), fb.calls)

    def test_audio_argument_overrides_midi(self):
        fb = FakeBackend()
        make_audio('song.mid', 'track.ogg', backend=fb)
        self.assertIn(('load', 'track.ogg'), fb.calls)
        self.assertNotIn(('load', 'song.mid'), fb.calls)

    def test_load_failure_degrades_to_silent(self):
        fb = FakeBackend(raise_on_load=True)
        audio = make_audio('song.mid', None, backend=fb)  # must not raise
        # Not loaded -> play() does not touch the backend.
        audio.play()
        self.assertNotIn(('play',), fb.calls)


if __name__ == '__main__':
    unittest.main()
