"""
src/ui/hud.py — 2D HUD / countdown / results overlay.

Draws the score/combo/accuracy panels, the DEMO badge, the 3-2-1 countdown, and
the results overlay onto a transparent SRCALPHA surface. The GL renderer uploads
this surface as a texture and composites it over the perspective playfield (see
SurfacePresenter). Being plain pygame, it is fully testable headlessly.

The playfield itself (lanes, falling notes, hit bar, key caps) is drawn by the GL
renderer; this module owns only the flat overlay.
"""
from __future__ import annotations

import pygame

from src.game.engine import GameState
from src.ui.skin import NeonArcadeSkin

# Colors used by the countdown / results overlays.
_TEXT = (235, 245, 255)

# Neon-arcade HUD layout at the 1366x768 shipping resolution. Left-column panels
# anchor to the left margin; the right column (score/combo) anchors to the right
# margin. The central inspection band Rect(448, 70, 470, 560) is intentionally
# left clear so the falling-note playfield stays visible underneath.
_BASE_SIZE = (1366, 768)
_SONG_RECT = pygame.Rect(28, 24, 404, 154)
_GAUGE_RECT = pygame.Rect(28, 194, 356, 88)
_STAT_RECT = pygame.Rect(28, 320, 174, 96)
_SCORE_RECT = pygame.Rect(940, 24, 398, 130)
_COMBO_RECT = pygame.Rect(998, 176, 340, 126)


class HudOverlay:
    """Draws the flat HUD/countdown/results layer onto a transparent surface.

    Layout/state only: the panel chrome is delegated to NeonArcadeSkin.
    """

    def __init__(self, size: tuple[int, int]) -> None:
        self.width, self.height = size
        pygame.font.init()
        self._font = pygame.font.SysFont('consolas,menlo,monospace', 22)
        self._big = pygame.font.SysFont('consolas,menlo,monospace', 120)
        self._mid = pygame.font.SysFont('consolas,menlo,monospace', 48)
        self._skin = NeonArcadeSkin()
        self._layout = self._build_layout(size)

    def render(self, target: pygame.Surface, scoring, *, state: GameState,
               countdown: int = 0, is_demo: bool = False) -> None:
        """Clear *target* to transparent and draw the overlay for *state*."""
        target.fill((0, 0, 0, 0))
        self._draw_hud(target, scoring, is_demo)

        if state is GameState.COUNTDOWN and countdown > 0:
            self._draw_center_text(target, str(countdown), self._big)
        elif state is GameState.FINISHED:
            self._draw_results(target, scoring)

    # --- pieces ------------------------------------------------------------

    def _draw_hud(self, target: pygame.Surface, scoring, is_demo: bool) -> None:
        song, gauge, stat, score, combo = self._layout
        # Song metadata isn't plumbed through yet (first pass): show a stable
        # title and the placeholder jacket. Wiring real metadata is a follow-up.
        self._skin.draw_song_panel(target, song, title='MIDIMANIA')
        self._skin.draw_gauge_panel(target, gauge, value=scoring.accuracy,
                                    label='ACCURACY')
        self._skin.draw_small_stat_box(
            target, stat, label='MODE', value='DEMO' if is_demo else 'LIVE',
            color='red' if is_demo else 'blue')
        self._skin.draw_score_panel(target, score, score=scoring.score)
        self._skin.draw_combo_panel(target, combo, combo=scoring.combo,
                                    full_combo=scoring.accuracy >= 1.0)

    def _draw_results(self, target: pygame.Surface, scoring) -> None:
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        target.blit(overlay, (0, 0))
        self._draw_center_text(target, f"RANK {scoring.rank()}", self._big, dy=-80)
        self._draw_center_text(target, f"{scoring.score}", self._mid, dy=30)
        self._draw_center_text(
            target, f"ACC {scoring.accuracy * 100:.1f}%   MAX COMBO {scoring.max_combo}",
            self._font, dy=90)

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _build_layout(size: tuple[int, int]) -> tuple[pygame.Rect, ...]:
        """Scale the base 1366x768 panel rects to *size*, anchoring columns.

        Left-column panels keep the left margin; the right column keeps the
        right margin, so the layout stays balanced at other resolutions."""
        width, height = size
        scale = min(width / _BASE_SIZE[0], height / _BASE_SIZE[1])
        right_margin = _BASE_SIZE[0] - _SCORE_RECT.right  # 28 px at base

        def place(rect: pygame.Rect, anchor: str) -> pygame.Rect:
            w, h = int(rect.width * scale), int(rect.height * scale)
            y = int(rect.y * scale)
            if anchor == 'right':
                x = width - int(right_margin * scale) - w
            else:
                x = int(rect.x * scale)
            return pygame.Rect(x, y, w, h)

        return (place(_SONG_RECT, 'left'), place(_GAUGE_RECT, 'left'),
                place(_STAT_RECT, 'left'), place(_SCORE_RECT, 'right'),
                place(_COMBO_RECT, 'right'))

    def _draw_center_text(self, target: pygame.Surface, text: str,
                          font: pygame.font.Font, dy: int = 0) -> None:
        surf = font.render(text, True, _TEXT)
        rect = surf.get_rect(center=(self.width // 2, self.height // 2 + dy))
        target.blit(surf, rect)
