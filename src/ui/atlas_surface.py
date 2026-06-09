"""Pygame atlas-surface preparation shared by GL and 2D renderers."""
from __future__ import annotations

import pygame

from src.ui import atlas


def prepare_atlas_surface(surface: pygame.Surface) -> pygame.Surface:
    """Return an SRCALPHA atlas copy with opaque FX backgrounds suppressed."""
    prepared = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    prepared.blit(surface, (0, 0))
    seen: set[tuple[int, int, int, int]] = set()
    for family, name in atlas.FX_ALPHA_KEY_REGIONS:
        rect = atlas.ATLAS_RECTS.get(family, {}).get(name)
        if rect is None or rect in seen:
            continue
        seen.add(rect)
        _key_dark_fx_pixels(prepared, pygame.Rect(rect))
    return prepared


def _key_dark_fx_pixels(surface: pygame.Surface, rect: pygame.Rect) -> None:
    for y in range(rect.top, rect.bottom):
        for x in range(rect.left, rect.right):
            r, g, b, a = surface.get_at((x, y))
            brightness = max(r, g, b)
            if brightness <= 20:
                factor = 0.0
            elif brightness >= 95:
                factor = 1.0
            else:
                factor = ((brightness - 20) / 75) ** 2
            surface.set_at((x, y), (
                int(r * factor), int(g * factor), int(b * factor),
                int(a * factor),
            ))
