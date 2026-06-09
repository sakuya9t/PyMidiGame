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
import random

import pygame

from src.ui.atlas import ATLAS_RECTS, nine_slice

Color = tuple[int, int, int]
Point = tuple[float, float]
Border = tuple[int, int, int, int]

# Default dark, translucent fill for nine-slice panel interiors.
_PANEL_INTERIOR = (8, 13, 24, 208)


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

    # Atlas sub-rects live in src/ui/atlas.py (shared with the GL AtlasTexture).
    _ATLAS_RECTS = ATLAS_RECTS

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

    def draw_nine_slice(self, surface: pygame.Surface, family: str, name: str,
                        rect: pygame.Rect, border: Border | None = None, *,
                        alpha: int = 255,
                        fill: tuple[int, int, int, int] = _PANEL_INTERIOR,
                        interior: pygame.Surface | None = None) -> bool:
        """Draw a nine-slice atlas panel, stretching edges but not corners.

        Corners blit at native size; the four edges stretch along one axis; the
        center is filled with *fill* (and an optional *interior* texture) rather
        than stretching the source middle, which may carry baked labels.

        Returns False — leaving *surface* untouched — when the atlas asset or a
        border is unavailable, or when *rect* is too small to hold the borders,
        so callers can fall back to drawn frames.
        """
        if border is None:
            border = nine_slice(family, name)
        if border is None:
            return False
        source = self._source(family, name)
        if source is None:
            return False

        left, top, right, bottom = border
        sw, sh = source.get_size()
        if rect.width < left + right or rect.height < top + bottom:
            return False
        if left + right >= sw or top + bottom >= sh:
            return False

        cw = rect.width - left - right       # center width (dest and src share it)
        ch = rect.height - top - bottom
        s_mid_w = sw - left - right
        s_mid_h = sh - top - bottom

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill(fill, pygame.Rect(left, top, cw, ch))
        if interior is not None:
            self._tile_into(panel, interior, pygame.Rect(left, top, cw, ch))

        def piece(sx: int, sy: int, pw: int, ph: int) -> pygame.Surface:
            return source.subsurface(pygame.Rect(sx, sy, pw, ph)).copy()

        # Corners (native size).
        panel.blit(piece(0, 0, left, top), (0, 0))
        panel.blit(piece(sw - right, 0, right, top), (rect.width - right, 0))
        panel.blit(piece(0, sh - bottom, left, bottom), (0, rect.height - bottom))
        panel.blit(piece(sw - right, sh - bottom, right, bottom),
                   (rect.width - right, rect.height - bottom))
        # Edges (stretched along one axis).
        panel.blit(pygame.transform.smoothscale(
            piece(left, 0, s_mid_w, top), (cw, top)), (left, 0))
        panel.blit(pygame.transform.smoothscale(
            piece(left, sh - bottom, s_mid_w, bottom), (cw, bottom)),
            (left, rect.height - bottom))
        panel.blit(pygame.transform.smoothscale(
            piece(0, top, left, s_mid_h), (left, ch)), (0, top))
        panel.blit(pygame.transform.smoothscale(
            piece(sw - right, top, right, s_mid_h), (right, ch)),
            (rect.width - right, top))

        if alpha < 255:
            panel.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(panel, rect.topleft)
        return True

    # --- glow text + runtime overlays -------------------------------------

    # Eight-direction halo offsets for the additive glow pass.
    _GLOW_OFFSETS = ((-2, 0), (2, 0), (0, -2), (0, 2),
                     (-1, -1), (1, 1), (-1, 1), (1, -1))

    def draw_glow_text(self, surface: pygame.Surface, font: pygame.font.Font,
                       text: str, pos: Point | pygame.Rect, color: Color,
                       glow_color: Color, *, align: str = 'left') -> pygame.Rect:
        """Draw *text* with an additive glow halo, crisp foreground on top.

        *pos* is a point (anchored per *align*: 'left'→topleft, 'center'→center,
        'right'→topright) or a Rect (the text is placed against the matching
        edge). Deterministic: no per-frame jitter. Returns the foreground rect.
        """
        base = font.render(text, True, color)
        rect = base.get_rect()
        if isinstance(pos, pygame.Rect):
            if align == 'center':
                rect.center = pos.center
            elif align == 'right':
                rect.midright = pos.midright
            else:
                rect.midleft = pos.midleft
        else:
            if align == 'center':
                rect.center = (int(pos[0]), int(pos[1]))
            elif align == 'right':
                rect.topright = (int(pos[0]), int(pos[1]))
            else:
                rect.topleft = (int(pos[0]), int(pos[1]))

        pad = 6
        glow = font.render(text, True, glow_color)
        halo = pygame.Surface((rect.width + pad * 2, rect.height + pad * 2),
                              pygame.SRCALPHA)
        for dx, dy in self._GLOW_OFFSETS:
            halo.blit(glow, (pad + dx, pad + dy),
                      special_flags=pygame.BLEND_RGBA_ADD)
        halo.fill((255, 255, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(halo, (rect.x - pad, rect.y - pad))
        surface.blit(base, rect)  # crisp foreground last
        return rect

    def draw_asset(self, surface: pygame.Surface, family: str, name: str,
                   rect: pygame.Rect, *, alpha: int = 255) -> bool:
        """Blit an atlas region with normal alpha (e.g. rank badges, icons).

        Returns False when the asset is unavailable, leaving *surface* untouched
        so callers can fall back to drawn art."""
        return self._blit_asset(surface, family, name, rect, alpha=alpha)

    def draw_additive_asset(self, surface: pygame.Surface, family: str,
                            name: str, rect: pygame.Rect, *,
                            alpha: int = 255) -> bool:
        """Blit an atlas asset additively (BLEND_RGBA_ADD) for glow/spark FX.

        Returns False if the asset is unavailable, leaving *surface* untouched."""
        asset = self._asset(family, name, rect.size)
        if asset is None:
            return False
        textured = asset.copy()
        if alpha < 255:
            textured.fill((255, 255, 255, alpha),
                          special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(textured, rect.topleft, special_flags=pygame.BLEND_RGBA_ADD)
        return True

    @staticmethod
    def make_noise_tile(size: tuple[int, int], *, seed: int = 0) -> pygame.Surface:
        """Deterministic sparse low-alpha noise tile for panel interiors."""
        w, h = size
        tile = pygame.Surface(size, pygame.SRCALPHA)
        rng = random.Random(seed)
        count = max(1, (w * h) // 22)
        palette = ((90, 170, 255), (255, 80, 110), (235, 245, 255))
        for _ in range(count):
            x = rng.randrange(w)
            y = rng.randrange(h)
            color = palette[rng.randrange(len(palette))]
            tile.set_at((x, y), (*color, rng.randint(8, 22)))
        return tile

    @staticmethod
    def make_scanline_tile(size: tuple[int, int] = (4, 4)) -> pygame.Surface:
        """Transparent tile with a single faint horizontal scanline."""
        w, h = size
        tile = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.line(tile, (255, 255, 255, 18), (0, 0), (w - 1, 0))
        return tile

    @staticmethod
    def load_optional_ui_image(path: str) -> pygame.Surface | None:
        """Load a UI image, or None if it is missing or unreadable.

        Avoids convert_alpha() when no display mode is set so it stays usable in
        headless tests; callers must keep working without the image."""
        if not path or not os.path.exists(path):
            return None
        try:
            surf = pygame.image.load(path)
        except pygame.error:
            return None
        try:
            return surf.convert_alpha()
        except pygame.error:
            return surf

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

    def _source(self, family: str, name: str) -> pygame.Surface | None:
        """Raw, unscaled atlas subsurface for a region, or None if unavailable.

        Used by nine-slice rendering, which slices the source at native pixels
        rather than pre-scaling the whole region."""
        if self._atlas is None:
            return None
        rect = self._ATLAS_RECTS.get(family, {}).get(name)
        if rect is None:
            return None
        x, y, w, h = rect
        try:
            return self._atlas.subsurface(pygame.Rect(x, y, w, h))
        except ValueError:
            return None

    @staticmethod
    def _tile_into(surface: pygame.Surface, tile: pygame.Surface,
                   region: pygame.Rect) -> None:
        """Repeat *tile* to cover *region* of *surface*, clipped to the region."""
        if region.width <= 0 or region.height <= 0:
            return
        prev_clip = surface.get_clip()
        surface.set_clip(region)
        tw, th = tile.get_size()
        for y in range(region.top, region.bottom, th):
            for x in range(region.left, region.right, tw):
                surface.blit(tile, (x, y))
        surface.set_clip(prev_clip)

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
