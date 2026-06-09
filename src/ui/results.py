"""
src/ui/results.py — standalone post-song results screen (DESIGN §15).

A full-screen summary shown after a run: song title/artist, big rank, score,
accuracy, the per-judgment breakdown (PERFECT/GREAT/GOOD/MISS), and max combo,
with a demo-mode banner and the retry/menu prompt. Unlike the in-game HUD's
FINISHED overlay, this replaces the playfield with an opaque screen.

Plain pygame drawing onto a surface (presented as a GL textured quad by the App),
so it is testable headlessly like the menu and HUD.
"""
from __future__ import annotations

import pygame

from src.ui.materials import NeonMaterialKit

# Colors
_BG = (5, 8, 18)
_EDGE = (30, 175, 255)
_TEXT = (235, 245, 255)
_MUTED = (120, 170, 220)
_DEMO = (255, 205, 80)
_CENTER = (255, 48, 70)

_RANK_COLORS = {
    'S': (255, 205, 80), 'A': (90, 240, 170), 'B': (90, 170, 255),
    'C': (200, 200, 210), 'D': (255, 110, 130),
}

# (label, attribute, color)
_JUDGMENTS = (
    ('PERFECT', 'perfect', (255, 205, 80)),
    ('GREAT', 'great', (90, 170, 255)),
    ('GOOD', 'good', (90, 240, 170)),
    ('MISS', 'miss', (255, 90, 110)),
)

# Rank letter -> atlas badge region. D has no badge (drawn letter fallback).
_RANK_BADGES = {'S': 'rank_s', 'A': 'rank_a', 'B': 'rank_b', 'C': 'rank_c'}


def rank_badge_name(rank: str) -> str | None:
    """Atlas badge region for a rank letter, or None to draw the letter."""
    return _RANK_BADGES.get(rank)


class ResultsScreen:
    """Draws the full results screen onto a surface."""

    def __init__(self, size: tuple[int, int]) -> None:
        self.width, self.height = size
        pygame.font.init()
        self._title = pygame.font.SysFont('consolas,menlo,monospace', 44, bold=True)
        self._artist = pygame.font.SysFont('consolas,menlo,monospace', 22)
        self._label = pygame.font.SysFont('consolas,menlo,monospace', 20, bold=True)
        self._value = pygame.font.SysFont('consolas,menlo,monospace', 40, bold=True)
        self._rank_letter = pygame.font.SysFont('consolas,menlo,monospace', 150, bold=True)
        self._count = pygame.font.SysFont('consolas,menlo,monospace', 34, bold=True)
        self._prompt = pygame.font.SysFont('consolas,menlo,monospace', 20)
        self._materials = NeonMaterialKit()

    def render(self, target: pygame.Surface, scoring, entry, input_mode: str) -> None:
        target.fill(_BG)
        self._draw_header(target, entry, input_mode)
        self._draw_rank_panel(target, scoring)
        self._draw_stats_panel(target, scoring)
        self._draw_judgments(target, scoring)
        if input_mode == 'demo':
            self._draw_demo_banner(target)
        self._draw_prompt(target)

    # --- pieces ------------------------------------------------------------

    def _draw_header(self, target, entry, input_mode: str) -> None:
        target.blit(self._title.render(entry.title, True, _TEXT), (60, 46))
        sub = entry.artist if entry.artist else '—'
        target.blit(self._artist.render(sub, True, _MUTED), (62, 104))
        mode = {'pc': 'PC KEYBOARD', 'demo': 'DEMO', 'midi': 'MIDI KEYBOARD'}.get(
            input_mode, input_mode.upper())
        meta = f"{entry.key_class}   ·   {mode}"
        target.blit(self._artist.render(meta, True, _EDGE), (62, 138))

    def _draw_rank_panel(self, target, scoring) -> None:
        rank = scoring.rank()
        color = _RANK_COLORS.get(rank, _TEXT)
        panel = pygame.Rect(60, 210, 360, 320)
        self._materials.draw_panel_frame(target, panel, color)
        self._blit_center(target, 'RANK', self._label, _MUTED,
                          (panel.centerx, panel.top + 44))
        center = (panel.centerx, panel.centery + 22)
        badge = rank_badge_name(rank)
        badge_rect = pygame.Rect(0, 0, 176, 176)
        badge_rect.center = center
        if not (badge and self._materials.draw_asset(target, 'rank', badge,
                                                     badge_rect)):
            # No atlas badge for this rank (or atlas missing): draw the letter.
            letter = self._rank_letter.render(rank, True, color)
            target.blit(letter, letter.get_rect(center=center))

    def _draw_stats_panel(self, target, scoring) -> None:
        panel = pygame.Rect(456, 210, self.width - 456 - 60, 320)
        self._materials.draw_panel_frame(target, panel, _EDGE)
        x = panel.left + 36
        self._draw_stat(target, 'SCORE', f"{scoring.score:07}", x, panel.top + 40)
        self._draw_stat(target, 'ACCURACY', f"{scoring.accuracy * 100:.1f}%",
                        x, panel.top + 130)
        self._draw_stat(target, 'MAX COMBO', f"{scoring.max_combo}",
                        x, panel.top + 220)

    def _draw_stat(self, target, label: str, value: str, x: int, y: int) -> None:
        target.blit(self._label.render(label, True, _MUTED), (x, y))
        target.blit(self._value.render(value, True, _TEXT), (x, y + 26))

    def _draw_judgments(self, target, scoring) -> None:
        top = 560
        cell_w = (self.width - 120) / len(_JUDGMENTS)
        for i, (label, attr, color) in enumerate(_JUDGMENTS):
            cx = 60 + cell_w * (i + 0.5)
            self._blit_center(target, label, self._label, color, (cx, top))
            self._blit_center(target, str(getattr(scoring, attr)), self._count,
                              _TEXT, (cx, top + 34))

    def _draw_demo_banner(self, target) -> None:
        text = 'DEMO MODE — connect a MIDI device to play yourself'
        self._blit_center(target, text, self._artist, _DEMO,
                          (self.width // 2, 642))

    def _draw_prompt(self, target) -> None:
        self._blit_center(target, 'R retry        Enter / Esc  menu', self._prompt,
                          _MUTED, (self.width // 2, self.height - 34))

    # --- helpers -----------------------------------------------------------

    def _blit_center(self, target, text: str, font: pygame.font.Font,
                     color: tuple[int, int, int], center: tuple[int, int]) -> None:
        surf = font.render(text, True, color)
        target.blit(surf, surf.get_rect(center=center))
