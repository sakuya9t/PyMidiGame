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
#
# The Phase-5 "neon arcade skin" rects (HUD frames, gauge polish, decorative
# accents, FX) are measured in resources/ui/neon_arcade_skin_resources.json and
# mirrored here so this module stays the single numeric source of truth. Some
# are deliberate aliases of the earlier note/panel rects (e.g. score_panel ==
# blue/panel, impact_spark == spark): the skin refers to them by their HUD role.
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
        # Phase 5 — HUD frames (nine-slice panels).
        'score_panel': (740, 67, 484, 101),
        'song_info_panel': (739, 340, 243, 104),
        'gauge_panel': (1009, 338, 209, 84),
        'small_stat_box': (744, 481, 123, 73),
        'generic_wide_panel': (894, 476, 342, 86),
        # Phase 5 — gauge polish.
        'gauge_overlay_glow': (740, 754, 490, 30),
        'meter_piece_full': (743, 820, 60, 25),
        # Phase 5 — decorative accents.
        'decor_corner': (18, 932, 37, 37),
        'decor_line': (18, 992, 377, 10),
        'arrows': (682, 1195, 90, 31),
        'screw_decal': (1110, 1198, 20, 20),
        # Phase 5 — FX and small UI.
        'impact_spark': (560, 1036, 110, 102),
        'glint_tiny': (706, 1045, 120, 80),
        'life_icon': (118, 1184, 60, 50),
        'multiplier_chip': (558, 1186, 66, 50),
    },
    'white': {
        'lane': (150, 72, 82, 498),
        'note': (500, 158, 84, 36),
        'hold': (500, 336, 82, 164),
        'key': (95, 646, 68, 62),
        'panel': (895, 486, 340, 68),
        'spark': (673, 1036, 110, 102),
        # Phase 5 — FX.
        'impact_spark': (673, 1036, 110, 102),
        'glint_tiny': (840, 1045, 165, 80),
    },
    'red': {
        'lane': (267, 72, 82, 498),
        'note': (611, 158, 84, 36),
        'hold': (612, 336, 82, 164),
        'key': (325, 646, 68, 62),
        'panel': (739, 214, 483, 90),
        'spark': (787, 1036, 110, 102),
        # Phase 5 — HUD frame + FX.
        'combo_panel': (739, 214, 483, 90),
        'impact_spark': (787, 1036, 110, 102),
        'glint_tiny': (1035, 1045, 185, 80),
    },
    # Phase 5 — results rank badges. A non-color family (no lane/note/panel
    # members); accessed by name only, so it never participates in the
    # color-family lookup that drives lanes/notes.
    'rank': {
        'rank_c': (201, 1177, 57, 60),
        'rank_b': (266, 1177, 57, 60),
        'rank_a': (331, 1177, 57, 60),
        'rank_s': (394, 1177, 57, 60),
        'rank_s_plus': (461, 1177, 58, 60),
    },
}

# family -> name -> (left, top, right, bottom) nine-slice border widths, in
# atlas pixels. Borders are preserved undistorted; edges stretch along one axis;
# the center stretches both ways. Measured in the skin spec; do not re-guess.
NINE_SLICE_BORDERS: dict[str, dict[str, tuple[int, int, int, int]]] = {
    'blue': {
        'score_panel': (42, 24, 50, 26),
        'song_info_panel': (92, 18, 30, 34),
        'gauge_panel': (46, 24, 46, 24),
        'small_stat_box': (34, 22, 34, 22),
        'generic_wide_panel': (44, 22, 44, 24),
    },
    'red': {
        'combo_panel': (42, 22, 44, 26),
    },
}

UV = tuple[float, float, float, float]
Border = tuple[int, int, int, int]


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


def nine_slice(family: str, name: str) -> Border | None:
    """Nine-slice border (left, top, right, bottom) for a panel, or None.

    Returns None for regions with no measured border (e.g. plain note/lane
    sprites), letting callers fall back to plain blitting or drawn frames."""
    return NINE_SLICE_BORDERS.get(family, {}).get(name)
