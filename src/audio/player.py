"""
src/audio/player.py — Audio player and timing authority.

Loads and plays an audio file via pygame.mixer and provides current_ms(), the
clock the game engine and scoring read. Satisfies the engine's Clock Protocol
(play/pause/resume/stop/current_ms/is_playing). See DESIGN.md §8.

Timing uses the wall clock (an injectable monotonic source) rather than the
audio backend's position query, so it is reliable and unit-testable without an
audio device. Paused time is excluded; AUDIO_OFFSET_MS is the A/V calibration
knob (positive shifts the audio clock forward).

Supported formats: MP3, OGG, WAV (pygame.mixer).
"""
from __future__ import annotations

import time
from typing import Callable

AUDIO_OFFSET_MS = 0.0


class _PygameBackend:
    """Real mixer backend. pygame is imported lazily so importing this module
    (and unit-testing with a fake backend) needs no audio device."""

    def load(self, path: str) -> None:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(path)

    def play(self) -> None:
        import pygame
        pygame.mixer.music.play()

    def pause(self) -> None:
        import pygame
        pygame.mixer.music.pause()

    def unpause(self) -> None:
        import pygame
        pygame.mixer.music.unpause()

    def stop(self) -> None:
        import pygame
        pygame.mixer.music.stop()


class AudioPlayer:
    """pygame.mixer-backed audio playback with a wall-clock timing authority."""

    def __init__(self, *, time_fn: Callable[[], float] = time.perf_counter,
                 backend=None, offset_ms: float = AUDIO_OFFSET_MS) -> None:
        self._time = time_fn
        self._backend = backend if backend is not None else _PygameBackend()
        self._offset = offset_ms
        self._start: float | None = None      # play() wall time; None = not playing
        self._paused = False
        self._pause_start = 0.0
        self._paused_duration = 0.0
        self._loaded = False

    def load(self, path: str) -> None:
        self._backend.load(path)
        self._loaded = True

    def play(self) -> None:
        self._start = self._time()
        self._paused = False
        self._paused_duration = 0.0
        if self._loaded:
            self._backend.play()

    def pause(self) -> None:
        if self._start is None or self._paused:
            return
        self._pause_start = self._time()
        self._paused = True
        if self._loaded:
            self._backend.pause()

    def resume(self) -> None:
        if not self._paused:
            return
        self._paused_duration += self._time() - self._pause_start
        self._paused = False
        if self._loaded:
            self._backend.unpause()

    def stop(self) -> None:
        if self._loaded:
            self._backend.stop()
        self._start = None
        self._paused = False

    def current_ms(self) -> float:
        """Milliseconds of playback elapsed, excluding paused time, plus offset.

        While paused, time is frozen at the pause instant. Returns 0.0 before
        play() and after stop().
        """
        if self._start is None:
            return 0.0
        now = self._pause_start if self._paused else self._time()
        return (now - self._start - self._paused_duration) * 1000.0 + self._offset

    def is_playing(self) -> bool:
        return self._start is not None and not self._paused
