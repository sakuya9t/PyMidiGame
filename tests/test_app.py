"""
Tests for src/app.py audio source resolution.

Precedence: an explicit --audio path, else a produced audio file paired with the
MIDI by name (song.mid -> song.ogg/.mp3/.wav/.flac), else a temporary WAV
preview synthesized from the MIDI. A load failure degrades to a silent run.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.app import build_keymap, make_audio, resolve_audio_source


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


class FakeSynthesizer:
    def __init__(self, raise_on_call=False):
        self.calls = []
        self._raise = raise_on_call

    def __call__(self, midi_path, *, chart=None):
        self.calls.append((midi_path, chart))
        if self._raise:
            raise RuntimeError('no synth')
        return 'generated-preview.wav'


class TestBuildKeymap(unittest.TestCase):

    def test_space_is_middle_lane_in_nine_lane_pc_layout(self):
        keymap = build_keymap(9)
        self.assertEqual(len(keymap), 9)
        self.assertEqual(keymap[pygame.K_SPACE], 4)
        self.assertNotIn(pygame.K_p, keymap)


class TestResolveAudioSource(unittest.TestCase):

    def test_explicit_audio_wins(self):
        src = resolve_audio_source('/songs/tune.mid', '/other/track.ogg',
                                   exists=lambda p: True)
        self.assertEqual(src, '/other/track.ogg')

    def test_discovers_paired_audio_next_to_midi(self):
        # song.ogg sits beside song.mid -> use it over the MIDI.
        paired = os.path.join('songs', 'tune.ogg')
        src = resolve_audio_source(os.path.join('songs', 'tune.mid'), None,
                                   exists=lambda p: p == paired)
        self.assertEqual(src, paired)

    def test_extension_precedence_prefers_ogg(self):
        # Both .ogg and .mp3 exist; .ogg wins.
        src = resolve_audio_source('tune.mid', None, exists=lambda p: True)
        self.assertEqual(src, 'tune.ogg')

    def test_falls_back_to_midi_when_no_paired_audio(self):
        src = resolve_audio_source('tune.mid', None, exists=lambda p: False)
        self.assertEqual(src, 'tune.mid')


class TestMakeAudio(unittest.TestCase):

    def test_loads_explicit_audio(self):
        fb = FakeBackend()
        synth = FakeSynthesizer()
        make_audio('song.mid', 'track.ogg', backend=fb, synthesizer=synth)
        self.assertIn(('load', 'track.ogg'), fb.calls)
        self.assertNotIn(('load', 'song.mid'), fb.calls)
        self.assertEqual(synth.calls, [])

    def test_synthesizes_midi_when_no_paired_audio(self):
        # No sibling audio for this synthetic path -> MIDI is rendered to WAV.
        fb = FakeBackend()
        synth = FakeSynthesizer()
        make_audio('no_such_song.mid', None, backend=fb, synthesizer=synth)
        self.assertEqual(synth.calls, [('no_such_song.mid', None)])
        self.assertIn(('load', 'generated-preview.wav'), fb.calls)
        self.assertNotIn(('load', 'no_such_song.mid'), fb.calls)

    def test_synthesizer_receives_chart(self):
        fb = FakeBackend()
        synth = FakeSynthesizer()
        chart = object()
        make_audio('song.mid', None, backend=fb, chart=chart, synthesizer=synth)
        self.assertEqual(synth.calls, [('song.mid', chart)])

    def test_load_failure_degrades_to_silent(self):
        fb = FakeBackend(raise_on_load=True)
        synth = FakeSynthesizer()
        audio = make_audio('song.mid', None, backend=fb, synthesizer=synth)  # must not raise
        audio.play()
        self.assertNotIn(('play',), fb.calls)  # nothing loaded -> backend untouched

    def test_synthesis_failure_degrades_to_silent(self):
        fb = FakeBackend()
        synth = FakeSynthesizer(raise_on_call=True)
        audio = make_audio('song.mid', None, backend=fb, synthesizer=synth)
        audio.play()
        self.assertEqual(fb.calls, [])


if __name__ == '__main__':
    unittest.main()
