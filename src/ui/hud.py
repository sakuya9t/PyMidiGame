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
from src.ui.materials import NeonMaterialKit

# Colors (shared palette with the former 2D renderer).
_BOARD_EDGE = (30, 175, 255)
_CENTER = (255, 48, 70)
_TEXT = (235, 245, 255)
_MUTED_TEXT = (120, 170, 220)
_DEMO = (255, 205, 80)


class HudOverlay:
    """Draws the flat HUD/countdown/results layer onto a transparent surface."""

    def __init__(self, size: tuple[int, int]) -> None:
        self.width, self.height = size
        pygame.font.init()
        self._font = pygame.font.SysFont('consolas,menlo,monospace', 22)
        self._big = pygame.font.SysFont('consolas,menlo,monospace', 120)
        self._mid = pygame.font.SysFont('consolas,menlo,monospace', 48)
        self._score = pygame.font.SysFont('consolas,menlo,monospace', 54, bold=True)
        self._materials = NeonMaterialKit()

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
        left = pygame.Rect(24, 22, 250, 116)
        self._draw_panel(target, left, _BOARD_EDGE)
        self._blit(target, "MIDIMANIA", left.x + 18, left.y + 16, color=_TEXT)
        self._blit(target, f"ACC {scoring.accuracy * 100:5.1f}%",
                   left.x + 18, left.y + 46, color=_MUTED_TEXT)
        self._draw_gauge(target, left.x + 18, left.y + 82, left.width - 36,
                         scoring.accuracy)

        score_panel = pygame.Rect(self.width - 310, 22, 286, 116)
        self._draw_panel(target, score_panel, _BOARD_EDGE)
        self._blit(target, "SCORE", score_panel.x + 18, score_panel.y + 12,
                   color=_BOARD_EDGE)
        score = self._score.render(f"{scoring.score:07}", True, _TEXT)
        target.blit(score, (score_panel.right - score.get_width() - 18,
                            score_panel.y + 42))

        combo_panel = pygame.Rect(self.width - 260, 156, 236, 92)
        self._draw_panel(target, combo_panel, _CENTER)
        self._blit(target, "COMBO", combo_panel.x + 18, combo_panel.y + 10,
                   color=_CENTER)
        combo = self._mid.render(f"{scoring.combo:04}", True, _TEXT)
        target.blit(combo, (combo_panel.right - combo.get_width() - 18,
                            combo_panel.y + 36))

        if is_demo:
            badge = self._font.render("DEMO", True, _DEMO)
            target.blit(badge, (self.width - badge.get_width() - 12, 10))

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

    def _draw_panel(self, target: pygame.Surface, rect: pygame.Rect,
                    color: tuple[int, int, int]) -> None:
        self._materials.draw_panel_frame(target, rect, color)

    def _draw_gauge(self, target: pygame.Surface, x: int, y: int,
                    width: int, value: float) -> None:
        rect = pygame.Rect(x, y - 4, width, 24)
        self._materials.draw_segmented_gauge(target, rect, _BOARD_EDGE, value)

    def _blit(self, target: pygame.Surface, text: str, x: int, y: int,
              *, color: tuple[int, int, int] = _TEXT) -> None:
        target.blit(self._font.render(text, True, color), (x, y))

    def _draw_center_text(self, target: pygame.Surface, text: str,
                          font: pygame.font.Font, dy: int = 0) -> None:
        surf = font.render(text, True, _TEXT)
        rect = surf.get_rect(center=(self.width // 2, self.height // 2 + dy))
        target.blit(surf, rect)
