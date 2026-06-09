"""
src/ui/skin.py — NeonArcadeSkin, the high-level neon-arcade HUD treatment.

This is the visual layer that sits between raw atlas drawing (NeonMaterialKit)
and HUD layout (HudOverlay). It owns *how* a score/combo/song/gauge/stat panel
looks: which atlas frame backs it, its glow colors and fonts, the interior
texture, and the small decorative accents. Callers pass a rect and the data to
show; they do not know how a panel is rendered.

Everything degrades gracefully: if the atlas image or the optional bitmap assets
(jacket placeholder, panel texture tile) are missing, panels fall back to drawn
frames and noise interiors, and nothing raises.
"""
from __future__ import annotations

import os

import pygame

from src.ui.materials import NeonMaterialKit

Point = tuple[float, float]
Color = tuple[int, int, int]

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_UI_DIR = os.path.join(_ROOT, 'resources', 'ui')
_DEFAULT_JACKET = os.path.join(_UI_DIR, 'neon_arcade_jacket_placeholder.png')
_DEFAULT_PANEL_TILE = os.path.join(_UI_DIR, 'neon_arcade_panel_texture_tile.png')

# Palette: foreground (crisp) + glow color per accent.
_BLUE = (40, 120, 255)
_RED = (255, 60, 90)
_TEXT = (235, 245, 255)
_BLUE_TEXT = (150, 205, 255)
_RED_TEXT = (255, 200, 210)
_MUTED = (120, 170, 220)
_GOLD = (255, 210, 90)

# Fallback frame colors when no atlas asset is available.
_FALLBACK_FRAME = {'blue': (30, 175, 255), 'red': (255, 48, 70)}


class NeonArcadeSkin:
    """Draws richly-styled neon HUD panels onto pygame surfaces."""

    def __init__(self, materials: NeonMaterialKit | None = None, *,
                 jacket_path: str = _DEFAULT_JACKET,
                 panel_tile_path: str = _DEFAULT_PANEL_TILE) -> None:
        self._mat = materials or NeonMaterialKit()
        pygame.font.init()
        self._f_label = pygame.font.SysFont('consolas,menlo,monospace', 18, bold=True)
        self._f_small = pygame.font.SysFont('consolas,menlo,monospace', 22)
        self._f_title = pygame.font.SysFont('consolas,menlo,monospace', 26, bold=True)
        self._f_value = pygame.font.SysFont('consolas,menlo,monospace', 30, bold=True)
        self._f_score = pygame.font.SysFont('consolas,menlo,monospace', 50, bold=True)
        self._f_combo = pygame.font.SysFont('consolas,menlo,monospace', 44, bold=True)

        self._jacket = self._mat.load_optional_ui_image(jacket_path)
        self._interior = self._build_interior(panel_tile_path)

    # --- public panel API --------------------------------------------------

    def draw_score_panel(self, target: pygame.Surface, rect: pygame.Rect, *,
                         score: int) -> None:
        self._frame(target, rect, 'blue', 'score_panel')
        inner = self._inner(rect)
        self._mat.draw_glow_text(target, self._f_label, 'SCORE',
                                 (inner.left, inner.top), _BLUE_TEXT, _BLUE)
        self._mat.draw_glow_text(
            target, self._f_score, f'{int(score):07d}',
            (inner.right, inner.bottom - self._f_score.get_height()),
            _TEXT, _BLUE, align='right')
        self._accent_line(target, rect, _BLUE)

    def draw_combo_panel(self, target: pygame.Surface, rect: pygame.Rect, *,
                         combo: int, full_combo: bool = False) -> None:
        self._frame(target, rect, 'red', 'combo_panel')
        inner = self._inner(rect)
        self._mat.draw_glow_text(target, self._f_label, 'COMBO',
                                 (inner.left, inner.top), _RED_TEXT, _RED)
        self._mat.draw_glow_text(
            target, self._f_combo, f'{int(combo):04d}',
            (inner.right, inner.bottom - self._f_combo.get_height()),
            _TEXT, _RED, align='right')
        if full_combo:
            self._mat.draw_glow_text(target, self._f_label, 'FULL COMBO!',
                                     (inner.left, inner.bottom - 18),
                                     _GOLD, _RED)

    def draw_song_panel(self, target: pygame.Surface, rect: pygame.Rect, *,
                        title: str, artist: str | None = None,
                        bpm: float | int | None = None,
                        jacket: pygame.Surface | None = None) -> None:
        self._frame(target, rect, 'blue', 'song_info_panel')
        inner = self._inner(rect)
        box = pygame.Rect(inner.left, inner.top, inner.height, inner.height)
        self._draw_jacket(target, box, jacket)

        tx = box.right + 14
        ty = inner.top + 2
        self._mat.draw_glow_text(target, self._f_title, _fit(title, 14),
                                 (tx, ty), _TEXT, _BLUE)
        ty += self._f_title.get_height() + 4
        if artist:
            target.blit(self._f_small.render(_fit(artist, 18), True, _MUTED),
                        (tx, ty))
            ty += self._f_small.get_height() + 2
        if bpm is not None:
            target.blit(self._f_label.render(f'BPM {int(bpm)}', True, _BLUE_TEXT),
                        (tx, ty))

    def draw_gauge_panel(self, target: pygame.Surface, rect: pygame.Rect, *,
                         value: float, label: str = 'GAUGE') -> None:
        self._frame(target, rect, 'blue', 'gauge_panel')
        inner = self._inner(rect)
        target.blit(self._f_label.render(label, True, _BLUE_TEXT),
                    (inner.left, inner.top))
        bar = pygame.Rect(inner.left, inner.bottom - 24, inner.width, 22)
        self._mat.draw_segmented_gauge(target, bar, _FALLBACK_FRAME['blue'],
                                       value)
        filled = max(1, int(bar.width * max(0.0, min(1.0, value))))
        self._mat.draw_additive_asset(
            target, 'blue', 'gauge_overlay_glow',
            pygame.Rect(bar.left, bar.top - 3, filled, bar.height + 6), alpha=150)

    def draw_small_stat_box(self, target: pygame.Surface, rect: pygame.Rect, *,
                            label: str, value: str, color: str = 'blue') -> None:
        self._frame(target, rect, 'blue', 'small_stat_box')
        inner = self._inner(rect)
        target.blit(self._f_label.render(label, True, _MUTED),
                    (inner.left, inner.top))
        glow = _RED if color == 'red' else _BLUE
        self._mat.draw_glow_text(
            target, self._f_value, str(value),
            (inner.centerx, inner.bottom - 6), _TEXT, glow, align='center')

    def draw_hit_spark(self, target: pygame.Surface, center: Point, *,
                       family: str = 'blue', intensity: float = 1.0) -> None:
        intensity = max(0.0, min(1.5, intensity))
        size = int(58 * intensity)
        if size < 2:
            return
        cx, cy = int(center[0]), int(center[1])
        rect = pygame.Rect(cx - size, cy - size, size * 2, size * 2)
        alpha = int(220 * min(1.0, intensity))
        if not self._mat.draw_additive_asset(target, family, 'impact_spark',
                                             rect, alpha=alpha):
            self._mat.draw_spark(target, center, _FALLBACK_FRAME.get(family, _BLUE),
                                 size=size)
        self._mat.draw_additive_asset(
            target, family, 'glint_tiny',
            pygame.Rect(cx - size, cy - size // 2, size * 2, size), alpha=alpha)

    # --- internals ---------------------------------------------------------

    def _frame(self, target: pygame.Surface, rect: pygame.Rect, family: str,
               name: str) -> None:
        if not self._mat.draw_nine_slice(target, family, name, rect,
                                         interior=self._interior):
            self._mat.draw_panel_frame(target, rect, _FALLBACK_FRAME[family])

    @staticmethod
    def _inner(rect: pygame.Rect) -> pygame.Rect:
        """Content rect inside a panel's frame border."""
        return rect.inflate(-44, -36)

    def _accent_line(self, target: pygame.Surface, rect: pygame.Rect,
                     color: Color) -> None:
        y = rect.top + 12
        self._mat.draw_additive_asset(
            target, 'blue', 'decor_line',
            pygame.Rect(rect.left + 22, y, min(120, rect.width - 60), 8),
            alpha=120)

    def _draw_jacket(self, target: pygame.Surface, box: pygame.Rect,
                     jacket: pygame.Surface | None) -> None:
        art = jacket if jacket is not None else self._jacket
        if art is not None:
            target.blit(pygame.transform.smoothscale(art, box.size), box.topleft)
        else:
            pygame.draw.rect(target, (12, 18, 32), box)
        pygame.draw.rect(target, _BLUE, box, width=2)

    def _build_interior(self, panel_tile_path: str) -> pygame.Surface:
        tile = self._mat.load_optional_ui_image(panel_tile_path)
        if tile is not None:
            interior = pygame.transform.smoothscale(tile, (128, 128))
            interior.fill((255, 255, 255, 50),
                          special_flags=pygame.BLEND_RGBA_MULT)
            return interior
        return self._mat.make_noise_tile((96, 96), seed=11)


def _fit(text: str, limit: int) -> str:
    """Truncate overly long labels so they stay inside a panel."""
    return text if len(text) <= limit else text[:limit - 1] + '…'
