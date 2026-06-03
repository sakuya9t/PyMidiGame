"""
Reusable neon UI materials for the pygame renderer.

The source texture reference is an atlas-style sheet: lane strips, note caps,
button panels, HUD frames, gauge segments, and spark effects. This module loads
the saved atlas when available and uses procedural drawing as a fallback and
finishing layer.
"""
from __future__ import annotations

import os
import math

import pygame

Color = tuple[int, int, int]
Point = tuple[float, float]


def _clamp(value: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, value))


def _scale(color: Color, factor: float) -> Color:
    return tuple(_clamp(int(c * factor)) for c in color)


def _mix(a: Color, b: Color, amount: float) -> Color:
    return tuple(_clamp(int(a[i] + (b[i] - a[i]) * amount)) for i in range(3))


def _beveled_rect_points(rect: pygame.Rect, bevel: int) -> list[Point]:
    bevel = max(2, min(bevel, rect.width // 3, rect.height // 3))
    return [
        (rect.left + bevel, rect.top), (rect.right - bevel, rect.top),
        (rect.right, rect.top + bevel), (rect.right, rect.bottom - bevel),
        (rect.right - bevel, rect.bottom), (rect.left + bevel, rect.bottom),
        (rect.left, rect.bottom - bevel), (rect.left, rect.top + bevel),
    ]


def _interp_x(a: Point, b: Point, y: float) -> float:
    if b[1] == a[1]:
        return a[0]
    t = (y - a[1]) / (b[1] - a[1])
    return a[0] + (b[0] - a[0]) * t


class NeonMaterialKit:
    """Draws small atlas-inspired neon materials onto pygame surfaces."""

    _ATLAS_RECTS = {
        'blue': {
            'lane': (34, 72, 82, 498),
            'hit': (389, 63, 316, 16),
            'note': (389, 158, 84, 36),
            'hold': (389, 336, 82, 164),
            'key': (18, 646, 80, 62),
            'panel': (740, 67, 484, 101),
            'gauge_empty': (740, 629, 488, 23),
            'gauge_filled': (740, 693, 488, 23),
            'spark': (560, 1036, 110, 102),
        },
        'white': {
            'lane': (150, 72, 82, 498),
            'note': (500, 158, 84, 36),
            'hold': (500, 336, 82, 164),
            'key': (95, 646, 68, 62),
            'panel': (895, 486, 340, 68),
            'spark': (673, 1036, 110, 102),
        },
        'red': {
            'lane': (267, 72, 82, 498),
            'note': (611, 158, 84, 36),
            'hold': (612, 336, 82, 164),
            'key': (325, 646, 68, 62),
            'panel': (739, 214, 483, 90),
            'spark': (787, 1036, 110, 102),
        },
    }

    def __init__(self, atlas_path: str | None = None) -> None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.atlas_path = atlas_path or os.path.join(
            root, 'resources', 'ui', 'neon_texture_atlas.png')
        self._atlas: pygame.Surface | None = None
        self._cache: dict[tuple[str, str, tuple[int, int]], pygame.Surface] = {}
        if os.path.exists(self.atlas_path):
            try:
                self._atlas = pygame.image.load(self.atlas_path)
            except pygame.error:
                self._atlas = None

    @property
    def using_atlas(self) -> bool:
        return self._atlas is not None

    def draw_lane_strip(self, surface: pygame.Surface, quad: list[Point],
                        color: Color, *, center: bool = False) -> None:
        family = self._family(color)
        used_atlas = self._draw_asset_quad(surface, family, 'lane', quad, alpha=235)
        if used_atlas:
            pygame.draw.polygon(surface, (*color, 72 if center else 42), quad, width=3)
            return

        fill_alpha = 48 if center else 32
        pygame.draw.polygon(surface, (*_scale(color, 0.45), fill_alpha), quad)
        pygame.draw.polygon(surface, (*color, 34), quad, width=4)

        top_y = min(p[1] for p in quad)
        bottom_y = max(p[1] for p in quad)
        left_top, right_top, right_bottom, left_bottom = quad

        step = 18
        y = top_y + 10
        while y < bottom_y - 4:
            left = _interp_x(left_top, left_bottom, y)
            right = _interp_x(right_top, right_bottom, y)
            alpha = 22 if int((y - top_y) / step) % 2 == 0 else 10
            pygame.draw.line(surface, (*color, alpha), (left + 4, y), (right - 4, y), 1)
            y += step

        for i in range(18):
            t = (i + 0.7) / 19
            y = top_y + (bottom_y - top_y) * t
            left = _interp_x(left_top, left_bottom, y)
            right = _interp_x(right_top, right_bottom, y)
            x = left + (right - left) * ((i * 37) % 100) / 100
            pygame.draw.rect(surface, (*_mix(color, (255, 255, 255), 0.3), 34),
                             pygame.Rect(int(x), int(y), 2, 2))

    def draw_hold_body(self, surface: pygame.Surface, quad: list[Point],
                       color: Color) -> None:
        used_atlas = self._draw_asset_quad(surface, self._family(color), 'hold',
                                           quad, alpha=235)
        if used_atlas:
            pygame.draw.polygon(surface, (*color, 82), quad, width=3)
            pygame.draw.line(surface, (*_mix(color, (255, 255, 255), 0.45), 165),
                             quad[0], quad[3], 2)
            pygame.draw.line(surface, (*_mix(color, (255, 255, 255), 0.45), 165),
                             quad[1], quad[2], 2)
            return

        pygame.draw.polygon(surface, (*_scale(color, 0.65), 84), quad)
        pygame.draw.polygon(surface, (*color, 58), quad, width=5)
        pygame.draw.line(surface, (*_mix(color, (255, 255, 255), 0.45), 145),
                         quad[0], quad[3], 2)
        pygame.draw.line(surface, (*_mix(color, (255, 255, 255), 0.45), 145),
                         quad[1], quad[2], 2)

        top_y = min(p[1] for p in quad)
        bottom_y = max(p[1] for p in quad)
        left_top, right_top, right_bottom, left_bottom = quad
        for y in range(int(top_y) + 8, int(bottom_y), 14):
            left = _interp_x(left_top, left_bottom, y)
            right = _interp_x(right_top, right_bottom, y)
            pygame.draw.line(surface, (*_mix(color, (255, 255, 255), 0.2), 20),
                             (left + 3, y), (right - 3, y), 1)

    def draw_note_cap(self, surface: pygame.Surface, rect: pygame.Rect,
                      color: Color) -> None:
        bevel = max(4, min(12, rect.width // 7, rect.height // 2))
        points = _beveled_rect_points(rect, bevel)
        glow = rect.inflate(18, 16)
        used_atlas = self._blit_asset(surface, self._family(color), 'note',
                                      glow, alpha=255)
        if used_atlas:
            pygame.draw.polygon(surface, _mix(color, (255, 255, 255), 0.5),
                                points, width=2)
            return

        pygame.draw.rect(surface, (*color, 54), glow, border_radius=bevel + 3)
        pygame.draw.polygon(surface, (*_scale(color, 0.55), 235), points)
        pygame.draw.polygon(surface, color, points, width=3)
        inner = rect.inflate(-8, -8)
        if inner.width > 3 and inner.height > 3:
            pygame.draw.polygon(surface, _mix(color, (255, 255, 255), 0.76),
                                _beveled_rect_points(inner, max(2, bevel - 4)),
                                width=2)
        pygame.draw.line(surface, (255, 255, 255, 150),
                         (rect.left + bevel, rect.top + 3),
                         (rect.right - bevel, rect.top + 3), 1)

    def draw_key_cap(self, surface: pygame.Surface, rect: pygame.Rect,
                     color: Color, *, active: bool = False) -> None:
        bevel = max(6, min(14, rect.width // 7, rect.height // 3))
        points = _beveled_rect_points(rect, bevel)
        fill = _scale(color, 0.34 if not active else 0.58)
        used_atlas = self._blit_asset(surface, self._family(color), 'key',
                                      rect.inflate(8, 8),
                                      alpha=255 if active else 225)
        if used_atlas:
            pygame.draw.polygon(surface, _mix(color, (255, 255, 255), 0.45),
                                points, width=1)
            return

        pygame.draw.rect(surface, (*color, 52 if active else 34),
                         rect.inflate(12, 10), border_radius=bevel + 2)
        pygame.draw.polygon(surface, (*fill, 230), points)
        pygame.draw.polygon(surface, color, points, width=2)
        inner = rect.inflate(-7, -7)
        if inner.width > 3 and inner.height > 3:
            pygame.draw.polygon(surface, _mix(color, (255, 255, 255), 0.64),
                                _beveled_rect_points(inner, max(3, bevel - 4)),
                                width=1)
        for y in range(rect.top + 9, rect.bottom - 5, 8):
            pygame.draw.line(surface, (*color, 26), (rect.left + bevel, y),
                             (rect.right - bevel, y), 1)

    def draw_panel_frame(self, surface: pygame.Surface, rect: pygame.Rect,
                         color: Color, *, cut: int = 16) -> None:
        points = _beveled_rect_points(rect, cut)
        glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(glow, (0, 0, 0, 150), points)
        pygame.draw.polygon(glow, (*color, 64), points, width=5)
        surface.blit(glow, (0, 0))
        used_atlas = self._blit_asset(surface, self._family(color), 'panel',
                                      rect, alpha=255)
        if used_atlas:
            pygame.draw.polygon(surface, color, points, width=1)
            self._draw_panel_accents(surface, rect, color)
            return

        inner = rect.inflate(-14, -14)
        inner_points = _beveled_rect_points(inner, max(5, cut - 8))
        pygame.draw.polygon(surface, color, points, width=1)
        pygame.draw.polygon(surface, (*_mix(color, (255, 255, 255), 0.38), 160),
                            inner_points, width=1)

        self._draw_panel_accents(surface, rect, color)

    def _draw_panel_accents(self, surface: pygame.Surface, rect: pygame.Rect,
                            color: Color) -> None:
        top_y = rect.top + 8
        bottom_y = rect.bottom - 8
        pygame.draw.line(surface, color, (rect.left + 28, top_y),
                         (rect.left + 92, top_y), 2)
        pygame.draw.line(surface, color, (rect.right - 122, bottom_y),
                         (rect.right - 36, bottom_y), 2)
        for i in range(5):
            x = rect.right - 80 + i * 10
            pygame.draw.line(surface, (*color, 170), (x, rect.top + 18),
                             (x + 1, rect.top + 18), 2)

    def draw_segmented_gauge(self, surface: pygame.Surface, rect: pygame.Rect,
                             color: Color, value: float, *, segments: int = 18) -> None:
        value = max(0.0, min(1.0, value))
        if self._blit_asset(surface, 'blue', 'gauge_empty', rect, alpha=245):
            filled_rect = pygame.Rect(rect.left, rect.top,
                                      max(1, int(rect.width * value)), rect.height)
            filled = self._asset('blue', 'gauge_filled', rect.size)
            if filled is not None:
                clipped = filled.subsurface(
                    pygame.Rect(0, 0, filled_rect.width, rect.height)).copy()
                clipped.set_alpha(255)
                surface.blit(clipped, filled_rect)
            return

        pygame.draw.polygon(surface, (*_scale(color, 0.25), 230),
                            _beveled_rect_points(rect, 8))
        pygame.draw.polygon(surface, color, _beveled_rect_points(rect, 8), width=1)

        filled = int(value * segments + 0.5)
        pad = 6
        gap = 3
        seg_w = max(4, (rect.width - pad * 2 - gap * (segments - 1)) // segments)
        seg_h = rect.height - pad * 2
        for i in range(segments):
            x = rect.left + pad + i * (seg_w + gap)
            seg = pygame.Rect(x, rect.top + pad, seg_w, seg_h)
            seg_color = color if i < filled else _scale(color, 0.16)
            pygame.draw.polygon(surface, (*seg_color, 235),
                                _beveled_rect_points(seg, 3))

        glow_y = rect.top - 5
        pygame.draw.line(surface, (*_mix(color, (255, 255, 255), 0.35), 100),
                         (rect.left + 5, glow_y), (rect.right - 5, glow_y), 3)

    def draw_spark(self, surface: pygame.Surface, center: tuple[float, float],
                   color: Color, *, size: int = 34) -> None:
        cx, cy = center
        spark = self._asset(self._family(color), 'spark', (size * 2, size * 2))
        if spark is not None:
            textured = spark.copy()
            textured.set_alpha(220)
            surface.blit(textured, (int(cx - size), int(cy - size)))
            return

        for i in range(16):
            angle = i * math.tau / 16
            length = size * (0.35 + ((i * 7) % 9) / 12)
            x = cx + math.cos(angle) * length
            y = cy + math.sin(angle) * length
            alpha = 180 if i % 4 == 0 else 96
            pygame.draw.line(surface, (*color, alpha), (cx, cy), (x, y), 2)
        pygame.draw.circle(surface, (255, 255, 255, 235), (int(cx), int(cy)), 4)
        pygame.draw.circle(surface, (*color, 96), (int(cx), int(cy)), size // 2, 2)

    def draw_hit_line(self, surface: pygame.Surface, start: Point,
                      end: Point) -> None:
        left = min(start[0], end[0])
        top = min(start[1], end[1]) - 8
        width = max(1, int(abs(end[0] - start[0])))
        rect = pygame.Rect(int(left), int(top), width, 18)
        if self._blit_asset(surface, 'blue', 'hit', rect, alpha=255):
            return
        pygame.draw.line(surface, (235, 245, 255, 160), start, end, 6)

    def _family(self, color: Color) -> str:
        if color[0] > 180 and color[1] < 140:
            return 'red'
        if min(color) > 170:
            return 'white'
        return 'blue'

    def _asset(self, family: str, name: str,
               size: tuple[int, int]) -> pygame.Surface | None:
        if self._atlas is None or size[0] <= 0 or size[1] <= 0:
            return None
        rect = self._ATLAS_RECTS.get(family, {}).get(name)
        if rect is None:
            return None
        key = (family, name, size)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        x, y, w, h = rect
        try:
            source = self._atlas.subsurface(pygame.Rect(x, y, w, h))
        except ValueError:
            return None
        asset = pygame.transform.smoothscale(source, size)
        textured = pygame.Surface(size, pygame.SRCALPHA)
        textured.blit(asset, (0, 0))
        self._cache[key] = textured
        return textured

    def _blit_asset(self, surface: pygame.Surface, family: str, name: str,
                    rect: pygame.Rect, *, alpha: int) -> bool:
        asset = self._asset(family, name, rect.size)
        if asset is None:
            return False
        textured = asset.copy()
        textured.set_alpha(alpha)
        surface.blit(textured, rect)
        return True

    def _draw_asset_quad(self, surface: pygame.Surface, family: str, name: str,
                         quad: list[Point], *, alpha: int) -> bool:
        min_x = int(min(p[0] for p in quad))
        max_x = int(max(p[0] for p in quad))
        min_y = int(min(p[1] for p in quad))
        max_y = int(max(p[1] for p in quad))
        bounds = pygame.Rect(min_x, min_y, max(1, max_x - min_x),
                             max(1, max_y - min_y))
        asset = self._asset(family, name, bounds.size)
        if asset is None:
            return False
        textured = asset.copy()
        textured.set_alpha(alpha)
        mask = pygame.Surface(bounds.size, pygame.SRCALPHA)
        local = [(x - bounds.x, y - bounds.y) for x, y in quad]
        pygame.draw.polygon(mask, (255, 255, 255, 255), local)
        textured.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(textured, bounds)
        return True
