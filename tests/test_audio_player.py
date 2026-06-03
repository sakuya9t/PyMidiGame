"""
Unit tests for src/audio/player.py — AudioPlayer.

The clock math (current_ms, pause/resume exclusion, offset) is tested headlessly
by injecting a controllable time source and a fake mixer backend, so no audio
device is required. AudioPlayer satisfies the engine's Clock Protocol.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.audio.player import AudioPlayer


class FakeTime:
    """Controllable monotonic source in seconds."""
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeBackend:
    """Records mixer calls instead of touching pygame."""
    def __init__(self):
        self.calls = []

    def load(self, path):
        self.calls.append(('load', path))

    def play(self):
        self.calls.append(('play',))

    def pause(self):
        self.calls.append(('pause',))

    def unpause(self):
        self.calls.append(('unpause',))

    def stop(self):
        self.calls.append(('stop',))


def _player(offset_ms=0.0):
    clock = FakeTime()
    backend = FakeBackend()
    player = AudioPlayer(time_fn=clock, backend=backend, offset_ms=offset_ms)
    return player, clock, backend


class TestClockMath(unittest.TestCase):

    def test_current_ms_before_play_is_zero(self):
        player, clock, backend = _player()
        self.assertEqual(player.current_ms(), 0.0)

    def test_advances_with_wall_clock(self):
        player, clock, backend = _player()
        player.play()
        clock.t = 5.0
        self.assertAlmostEqual(player.current_ms(), 5000.0)

    def test_pause_freezes_time(self):
        player, clock, backend = _player()
        player.play()
        clock.t = 5.0
        player.pause()
        clock.t = 7.0  # 2 s pass while paused
        self.assertAlmostEqual(player.current_ms(), 5000.0)

    def test_resume_excludes_paused_duration(self):
        player, clock, backend = _player()
        player.play()
        clock.t = 5.0
        player.pause()
        clock.t = 7.0
        player.resume()
        clock.t = 8.0  # 1 s of real play after resume
        self.assertAlmostEqual(player.current_ms(), 6000.0)

    def test_offset_applied(self):
        player, clock, backend = _player(offset_ms=50.0)
        player.play()
        clock.t = 5.0
        self.assertAlmostEqual(player.current_ms(), 5050.0)


class TestIsPlaying(unittest.TestCase):

    def test_state_transitions(self):
        player, clock, backend = _player()
        self.assertFalse(player.is_playing())
        player.play()
        self.assertTrue(player.is_playing())
        player.pause()
        self.assertFalse(player.is_playing())
        player.resume()
        self.assertTrue(player.is_playing())
        player.stop()
        self.assertFalse(player.is_playing())


class TestBackendForwarding(unittest.TestCase):

    def test_calls_forwarded(self):
        player, clock, backend = _player()
        player.load('song.ogg')
        player.play()
        player.pause()
        player.resume()
        player.stop()
        self.assertEqual(backend.calls, [
            ('load', 'song.ogg'), ('play',), ('pause',), ('unpause',), ('stop',),
        ])

    def test_redundant_pause_resume_are_safe(self):
        player, clock, backend = _player()
        player.load('song.ogg')
        player.play()
        player.resume()  # not paused -> no-op
        player.pause()
        player.pause()   # already paused -> no-op
        # Only one pause forwarded, no stray unpause.
        self.assertEqual(backend.calls.count(('pause',)), 1)
        self.assertEqual(backend.calls.count(('unpause',)), 0)


class TestNoAudioLoaded(unittest.TestCase):
    """Demo mode runs without an audio file: AudioPlayer is a pure wall clock
    and must not touch the mixer backend (which would raise 'music not loaded')."""

    def test_play_without_load_does_not_touch_backend(self):
        player, clock, backend = _player()
        player.play()
        self.assertEqual(backend.calls, [])

    def test_lifecycle_without_load_does_not_touch_backend(self):
        player, clock, backend = _player()
        player.play()
        player.pause()
        player.resume()
        player.stop()
        self.assertEqual(backend.calls, [])

    def test_clock_still_advances_without_audio(self):
        player, clock, backend = _player()
        player.play()
        clock.t = 3.0
        self.assertAlmostEqual(player.current_ms(), 3000.0)
        self.assertTrue(player.is_playing())


if __name__ == '__main__':
    unittest.main()
