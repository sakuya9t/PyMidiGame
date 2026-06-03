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
from src.ui.materials import NeonMaterialKit

LOOKAHEAD_MS = 2000.0  # how far ahead (ms) the top of the board shows

# Colors
_BG = (4, 7, 18)
_BOARD = (8, 12, 22)
_BOARD_EDGE = (30, 175, 255)
_LANE_LINE = (210, 230, 255)
_CENTER = (255, 48, 70)
_NOTE_BLUE = (20, 140, 255)
_NOTE_WHITE = (235, 238, 245)
_NOTE_HIT = (90, 240, 170)
_NOTE_MISS = (95, 45, 70)
_TEXT = (235, 245, 255)
_MUTED_TEXT = (120, 170, 220)
_DEMO = (255, 205, 80)

_PC_KEY_LABELS = ("A", "S", "D", "F", "SPACE", "J", "K", "L", ";")


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
        self.top_y = self.height * 0.05
        self.board_bottom_y = self.height * 0.91
        self.hit_y = self.height * 0.84
        self.pixels_per_ms = self.hit_y / LOOKAHEAD_MS
        pygame.font.init()
        self._font = pygame.font.SysFont('consolas,menlo,monospace', 22)
        self._small = pygame.font.SysFont('consolas,menlo,monospace', 16, bold=True)
        self._big = pygame.font.SysFont('consolas,menlo,monospace', 120)
        self._mid = pygame.font.SysFont('consolas,menlo,monospace', 48)
        self._score = pygame.font.SysFont('consolas,menlo,monospace', 54, bold=True)
        self._materials = NeonMaterialKit()

    def render(self, target: pygame.Surface, chart: Chart, current_ms: float,
               scoring: ScoringEngine, *, state: GameState,
               countdown: int = 0, is_demo: bool = False) -> None:
        target.fill(_BG)
        self._draw_backdrop(target)
        self._draw_lanes(target, chart.lane_count)
        self._draw_notes(target, chart, current_ms)
        self._draw_key_caps(target, chart)
        self._draw_hud(target, scoring, is_demo)

        if state is GameState.COUNTDOWN and countdown > 0:
            self._draw_center_text(target, str(countdown), self._big)
        elif state is GameState.FINISHED:
            self._draw_results(target, scoring)

    # --- pieces ------------------------------------------------------------

    def _draw_backdrop(self, target: pygame.Surface) -> None:
        horizon = int(self.top_y)
        center = (self.width // 2, horizon)
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        for x in range(-80, self.width + 120, 120):
            color = (35, 120, 255, 42) if x % 240 == 0 else (255, 35, 180, 32)
            pygame.draw.line(overlay, color, center, (x, self.height), 2)

        for y in range(horizon, self.height, 86):
            alpha = max(12, 65 - int((y - horizon) * 0.08))
            pygame.draw.line(overlay, (24, 70, 150, alpha), (0, y), (self.width, y), 1)

        target.blit(overlay, (0, 0))

    def _draw_lanes(self, target: pygame.Surface, lane_count: int) -> None:
        top_l, top_r = self._track_edges(self.top_y)
        bot_l, bot_r = self._track_edges(self.board_bottom_y)
        board = [(top_l, self.top_y), (top_r, self.top_y),
                 (bot_r, self.board_bottom_y), (bot_l, self.board_bottom_y)]
        pygame.draw.polygon(target, _BOARD, board)

        lane_overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        if lane_count <= 16:
            mid = lane_count // 2 if lane_count % 2 == 1 else -1
            for lane in range(lane_count):
                self._materials.draw_lane_strip(
                    lane_overlay,
                    self._lane_quad(lane, lane_count, self.top_y,
                                    self.board_bottom_y),
                    self._lane_note_color(lane, lane_count),
                    center=lane == mid,
                )

        for i in range(12):
            t = (i + 1) / 13
            y = self.top_y + (self.board_bottom_y - self.top_y) * (t ** 1.55)
            left, right = self._track_edges(y)
            pygame.draw.line(lane_overlay, (60, 100, 140, 55),
                             (left, y), (right, y), 1)

        for i in range(lane_count + 1):
            color = _CENTER if lane_count % 2 == 1 and i in (lane_count // 2, lane_count // 2 + 1) else _LANE_LINE
            top = self._lane_boundary_point(i, lane_count, self.top_y)
            bottom = self._lane_boundary_point(i, lane_count, self.board_bottom_y)
            pygame.draw.line(lane_overlay, (*color, 42), top, bottom, 7)
            pygame.draw.line(lane_overlay, (*color, 135), top, bottom, 2)
            pygame.draw.line(target, color, top, bottom, 1)

        for start, end in (((top_l, self.top_y), (bot_l, self.board_bottom_y)),
                           ((top_r, self.top_y), (bot_r, self.board_bottom_y))):
            pygame.draw.line(lane_overlay, (*_BOARD_EDGE, 90), start, end, 13)
            pygame.draw.line(target, _BOARD_EDGE, start, end, 3)

        hit_left, hit_right = self._track_edges(self.hit_y)
        self._materials.draw_hit_line(lane_overlay,
                                      (hit_left, self.hit_y),
                                      (hit_right, self.hit_y))

        target.blit(lane_overlay, (0, 0))

    def _draw_notes(self, target: pygame.Surface, chart: Chart,
                    current_ms: float) -> None:
        note_overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        caps: list[tuple[int, int, float, tuple[int, int, int]]] = []
        for n in chart.notes:
            y = note_center_y(n.time_ms, current_ms, self.hit_y, self.pixels_per_ms)
            body = n.duration_ms * self.pixels_per_ms
            top = y - body
            if top > self.board_bottom_y + 40 or y < self.top_y - 30:
                continue

            color = _NOTE_MISS if n.missed else (_NOTE_HIT if n.hit else self._lane_note_color(n.lane, chart.lane_count))

            if body > 18:
                beam_top = max(self.top_y, top)
                beam_bottom = min(self.board_bottom_y, y)
                if beam_bottom > beam_top:
                    self._materials.draw_hold_body(
                        note_overlay,
                        self._note_beam_quad(n.lane, chart.lane_count,
                                             beam_top, beam_bottom),
                        color,
                    )

            caps.append((n.lane, chart.lane_count, y, color))
        target.blit(note_overlay, (0, 0))
        for lane, lane_count, y, color in caps:
            self._draw_note_cap(target, lane, lane_count, y, color)
            if abs(y - self.hit_y) < 14:
                self._materials.draw_spark(
                    target,
                    (self._lane_center_at(lane, lane_count, self.hit_y), self.hit_y),
                    color,
                    size=30,
                )

    def _draw_hud(self, target: pygame.Surface, scoring: ScoringEngine,
                  is_demo: bool) -> None:
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

    def _track_edges(self, y: float) -> tuple[float, float]:
        span = self.board_bottom_y - self.top_y
        t = 0.0 if span <= 0 else max(0.0, min(1.0, (y - self.top_y) / span))
        track_w = self.width * (0.26 + 0.58 * t)
        center = self.width * 0.5
        return center - track_w / 2, center + track_w / 2

    def _lane_boundary_point(self, index: int, lane_count: int,
                             y: float) -> tuple[float, float]:
        left, right = self._track_edges(y)
        x = left + (right - left) * index / lane_count
        return x, y

    def _lane_quad(self, lane: int, lane_count: int, y1: float,
                   y2: float) -> list[tuple[float, float]]:
        return [
            self._lane_boundary_point(lane, lane_count, y1),
            self._lane_boundary_point(lane + 1, lane_count, y1),
            self._lane_boundary_point(lane + 1, lane_count, y2),
            self._lane_boundary_point(lane, lane_count, y2),
        ]

    def _lane_center_at(self, lane: int, lane_count: int, y: float) -> float:
        left, right = self._track_edges(y)
        lane_w = (right - left) / lane_count
        return left + (lane + 0.5) * lane_w

    def _lane_width_at(self, lane_count: int, y: float) -> float:
        left, right = self._track_edges(y)
        return (right - left) / lane_count

    def _lane_note_color(self, lane: int, lane_count: int) -> tuple[int, int, int]:
        if lane_count % 2 == 1 and lane == lane_count // 2:
            return _CENTER
        return _NOTE_BLUE if lane % 2 == 0 else _NOTE_WHITE

    def _note_beam_quad(self, lane: int, lane_count: int, y1: float,
                        y2: float) -> list[tuple[float, float]]:
        w1 = self._lane_width_at(lane_count, y1) * 0.56
        w2 = self._lane_width_at(lane_count, y2) * 0.56
        x1 = self._lane_center_at(lane, lane_count, y1)
        x2 = self._lane_center_at(lane, lane_count, y2)
        return [(x1 - w1 / 2, y1), (x1 + w1 / 2, y1),
                (x2 + w2 / 2, y2), (x2 - w2 / 2, y2)]

    def _draw_note_cap(self, target: pygame.Surface,
                       lane: int, lane_count: int, y: float,
                       color: tuple[int, int, int]) -> None:
        lane_w = self._lane_width_at(lane_count, y)
        note_w = max(8, int(lane_w * 0.68))
        note_h = max(10, min(24, int(lane_w * 0.28)))
        cx = self._lane_center_at(lane, lane_count, y)
        rect = pygame.Rect(int(cx - note_w / 2), int(y - note_h / 2), note_w, note_h)

        self._materials.draw_note_cap(target, rect, color)

    def _draw_key_caps(self, target: pygame.Surface, chart: Chart) -> None:
        if chart.lane_count > 12:
            return

        cap_y = self.hit_y + 32
        cap_h = min(50, self.height - cap_y - 12)
        if cap_h < 24:
            return

        for lane in range(chart.lane_count):
            left, _ = self._lane_boundary_point(lane, chart.lane_count, cap_y)
            right, _ = self._lane_boundary_point(lane + 1, chart.lane_count, cap_y)
            inset = max(4, int((right - left) * 0.08))
            rect = pygame.Rect(int(left + inset), int(cap_y),
                               int(right - left - inset * 2), int(cap_h))
            color = self._lane_note_color(lane, chart.lane_count)
            active = chart.lane_count % 2 == 1 and lane == chart.lane_count // 2
            self._materials.draw_key_cap(target, rect, color, active=active)
            label = self._lane_label(chart, lane)
            font = self._small if label == "SPACE" else self._font
            surf = font.render(label, True, _TEXT)
            target.blit(surf, surf.get_rect(center=rect.center))

    def _lane_label(self, chart: Chart, lane: int) -> str:
        if chart.mode == 'pc' and chart.lane_count == len(_PC_KEY_LABELS):
            return _PC_KEY_LABELS[lane]
        return str(lane + 1)

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
