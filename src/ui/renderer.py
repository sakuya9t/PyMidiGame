"""
src/ui/renderer.py — In-game 2D renderer (pygame).

A first-playable lane renderer: notes fall down vertical lanes toward a hit bar
near the bottom; the HUD shows score, combo, accuracy, a DEMO badge, the 3-2-1
countdown, and a results overlay. Decoupled from the legacy `Store` — it reads a
`Chart`, the engine's `current_ms()` scroll position, and a `ScoringEngine`.

This is the v1 renderer. The DESIGN.md §13 OpenGL vanishing-point perspective is
a later visual upgrade; the geometry here (lane_x / note_center_y) is the same
mapping a perspective renderer would feed into its projection.

Note vertical mapping: a note at the current time sits on the hit bar; a note
LOOKAHEAD_MS in the future sits at the top of the board. `pixels_per_ms` is
`hit_y / LOOKAHEAD_MS`.
"""
from __future__ import annotations

import pygame

from src.game.chart import Chart
from src.game.engine import GameState
from src.game.scoring import ScoringEngine

LOOKAHEAD_MS = 2000.0  # how far ahead (ms) the top of the board shows

# Colors
_BG = (12, 14, 22)
_LANE_LINE = (40, 44, 60)
_HIT_BAR = (235, 235, 245)
_NOTE = (90, 170, 255)
_NOTE_HIT = (90, 230, 140)
_NOTE_MISS = (90, 60, 70)
_TEXT = (235, 235, 245)
_DEMO = (255, 200, 80)


def lane_x(lane: int, lane_count: int, width: int) -> float:
    """Pixel X of the center of *lane* across *width*."""
    lane_w = width / lane_count
    return (lane + 0.5) * lane_w


def note_center_y(time_ms: float, current_ms: float, hit_y: float,
                  pixels_per_ms: float) -> float:
    """Pixel Y of a note's center: hit bar at current time, rising into the future."""
    return hit_y - (time_ms - current_ms) * pixels_per_ms


class Renderer:
    """Draws one frame of the game onto a pygame target surface."""

    def __init__(self, size: tuple[int, int]) -> None:
        self.width, self.height = size
        self.hit_y = self.height * 0.85
        self.pixels_per_ms = self.hit_y / LOOKAHEAD_MS
        pygame.font.init()
        self._font = pygame.font.SysFont('consolas,menlo,monospace', 22)
        self._big = pygame.font.SysFont('consolas,menlo,monospace', 120)
        self._mid = pygame.font.SysFont('consolas,menlo,monospace', 48)

    def render(self, target: pygame.Surface, chart: Chart, current_ms: float,
               scoring: ScoringEngine, *, state: GameState,
               countdown: int = 0, is_demo: bool = False) -> None:
        target.fill(_BG)
        self._draw_lanes(target, chart.lane_count)
        self._draw_notes(target, chart, current_ms)
        self._draw_hud(target, scoring, is_demo)

        if state is GameState.COUNTDOWN and countdown > 0:
            self._draw_center_text(target, str(countdown), self._big)
        elif state is GameState.FINISHED:
            self._draw_results(target, scoring)

    # --- pieces ------------------------------------------------------------

    def _draw_lanes(self, target: pygame.Surface, lane_count: int) -> None:
        for i in range(1, lane_count):
            x = int(self.width * i / lane_count)
            pygame.draw.line(target, _LANE_LINE, (x, 0), (x, self.height))
        pygame.draw.line(target, _HIT_BAR, (0, int(self.hit_y)),
                         (self.width, int(self.hit_y)), 3)

    def _draw_notes(self, target: pygame.Surface, chart: Chart,
                    current_ms: float) -> None:
        lane_w = self.width / chart.lane_count
        note_w = max(6, int(lane_w * 0.82))
        for n in chart.notes:
            y = note_center_y(n.time_ms, current_ms, self.hit_y, self.pixels_per_ms)
            body = max(14.0, n.duration_ms * self.pixels_per_ms)
            top = y - body
            if top > self.height or y < -2:  # fully below the bar / above the top
                continue
            cx = lane_x(n.lane, chart.lane_count, self.width)
            rect = pygame.Rect(int(cx - note_w / 2), int(top), note_w, int(body))
            color = _NOTE_MISS if n.missed else (_NOTE_HIT if n.hit else _NOTE)
            pygame.draw.rect(target, color, rect, border_radius=4)

    def _draw_hud(self, target: pygame.Surface, scoring: ScoringEngine,
                  is_demo: bool) -> None:
        self._blit(target, f"SCORE {scoring.score:>7}", 12, 10)
        self._blit(target, f"COMBO {scoring.combo:>4}", 12, 38)
        self._blit(target, f"ACC {scoring.accuracy * 100:5.1f}%", 12, 66)
        if is_demo:
            badge = self._font.render("DEMO", True, _DEMO)
            target.blit(badge, (self.width - badge.get_width() - 12, 10))

    def _draw_results(self, target: pygame.Surface, scoring: ScoringEngine) -> None:
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        target.blit(overlay, (0, 0))
        self._draw_center_text(target, f"RANK {scoring.rank()}", self._big, dy=-80)
        self._draw_center_text(target, f"{scoring.score}", self._mid, dy=30)
        self._draw_center_text(
            target, f"ACC {scoring.accuracy * 100:.1f}%   MAX COMBO {scoring.max_combo}",
            self._font, dy=90)

    # --- helpers -----------------------------------------------------------

    def _blit(self, target: pygame.Surface, text: str, x: int, y: int) -> None:
        target.blit(self._font.render(text, True, _TEXT), (x, y))

    def _draw_center_text(self, target: pygame.Surface, text: str,
                          font: pygame.font.Font, dy: int = 0) -> None:
        surf = font.render(text, True, _TEXT)
        rect = surf.get_rect(center=(self.width // 2, self.height // 2 + dy))
        target.blit(surf, rect)
