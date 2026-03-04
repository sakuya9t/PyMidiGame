"""Cross-platform audio playback via pygame.mixer.

Replaces the old Windows-only MCI implementation.  The public API is
unchanged: create an AudioClip, then call play/pause/unpause/stop.

Limitation: pygame.mixer.music supports one active track at a time.
Multiple AudioClip instances will share the single music channel, so
only the most-recently-loaded instance is valid for playback control.
This is acceptable for the game's single-track music requirement.
"""

import pygame


def load(filename):
    """Return an AudioClip for the given filename."""
    return AudioClip(filename)


class AudioClip:
    def __init__(self, filename):
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self.filename = filename
        pygame.mixer.music.load(filename)
        self._paused = False

    def play(self, start_ms=None, end_ms=None):
        """Start playing from start_ms (default 0).  Returns immediately."""
        if end_ms is not None and end_ms < (start_ms or 0):
            return
        start_s = (start_ms / 1000.0) if start_ms else 0.0
        pygame.mixer.music.play(start=start_s)
        self._paused = False

    def pause(self):
        """Pause playback."""
        pygame.mixer.music.pause()
        self._paused = True

    def unpause(self):
        """Resume from pause."""
        pygame.mixer.music.unpause()
        self._paused = False

    def stop(self):
        """Stop and rewind."""
        pygame.mixer.music.stop()
        self._paused = False

    def isplaying(self):
        """True if currently playing (not paused, not stopped)."""
        return pygame.mixer.music.get_busy() and not self._paused

    def ispaused(self):
        """True if currently paused."""
        return self._paused

    def volume(self, level):
        """Set volume 0–100."""
        assert 0 <= level <= 100
        pygame.mixer.music.set_volume(level / 100.0)

    def milliseconds(self):
        """Total clip length in ms.  Returns 0; pygame.mixer.music does not
        expose file duration without decoding the whole file."""
        return 0

    def seconds(self):
        """Total clip length in seconds (rounded)."""
        return int(round(self.milliseconds() / 1000))
