"""
src/ui/atlas.py — shared neon texture-atlas region table.

Single source of truth for the `resources/ui/neon_texture_atlas.png` sub-rects,
used by both the 2D `NeonMaterialKit` (pygame blits) and the GL `AtlasTexture`
(UV-mapped quads). Pure data + arithmetic: no pygame, no OpenGL imports, so it
stays headlessly testable and import-cheap.

Each rect is (x, y, w, h) in the atlas image's top-left pixel space. `uv()`
converts a named region to (u0, v0, u1, v1) texture coordinates with v flipped to
OpenGL's bottom-left origin (the atlas is uploaded flipped), so v0 is the region's
top edge and v1 its bottom edge.
"""
from __future__ import annotations

ATLAS_SIZE = (1254, 1254)

# family -> name -> (x, y, w, h) in atlas pixel space (top-left origin).
ATLAS_RECTS: dict[str, dict[str, tuple[int, int, int, int]]] = {
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

UV = tuple[float, float, float, float]


def uv(family: str, name: str) -> UV | None:
    """Texture coordinates (u0, v0, u1, v1) for a named region, or None if absent.

    v is flipped to OpenGL's bottom-left origin: v0 is the region's top edge,
    v1 its bottom edge (v0 > v1)."""
    rect = ATLAS_RECTS.get(family, {}).get(name)
    if rect is None:
        return None
    w, h = ATLAS_SIZE
    x, y, rw, rh = rect
    u0 = x / w
    u1 = (x + rw) / w
    v0 = 1.0 - y / h
    v1 = 1.0 - (y + rh) / h
    return (u0, v0, u1, v1)
