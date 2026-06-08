"""
src/ui/renderer.py — In-game OpenGL perspective renderer.

Draws the DJmax-style vanishing-point playfield: a board receding to a far
horizon, neon lanes, a hit bar, and note tiles that slide down the track and grow
toward the hit bar as their time arrives. Notes are placed along the Z axis from
their time vs. the engine's scroll position (current_ms); the perspective camera
turns that depth into the on-screen rise/shrink for free.

Texturing is first-class: the neon atlas is uploaded once (AtlasTexture) and
sampled onto lane/note/hold/hit-bar quads via the shared UV table, with a
flat-color fallback when the atlas is unavailable. The single `_textured_quad`
primitive is the seam for later visual effects (additive glow, animated UVs).

This module draws only the 3D scene. The flat HUD/countdown/results overlay is
drawn by HudOverlay and composited on top by the App via SurfacePresenter.
Drawing it needs an active GL context, so it is covered by a skip-guarded GL
smoke test rather than the headless suite; the placement math lives in the pure,
unit-tested src/ui/geometry.py.
"""
from __future__ import annotations

import pygame
from OpenGL.GL import (
    GL_BLEND, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST,
    GL_LINES, GL_MODELVIEW, GL_ONE_MINUS_SRC_ALPHA, GL_PROJECTION, GL_QUADS,
    GL_SRC_ALPHA, GL_TEXTURE_2D, glBegin, glBlendFunc, glClear, glClearColor,
    glColor4f, glDisable, glEnable, glEnd, glLineWidth, glLoadIdentity,
    glMatrixMode, glVertex3f, glTexCoord2f, glViewport,
)
from OpenGL.GLU import gluLookAt, gluPerspective

from src.game.chart import Chart
from src.ui import geometry
from src.ui.gl_textures import AtlasTexture

# --- world / camera constants ---------------------------------------------
BOARD_LEFT = -3.0
BOARD_RIGHT = 3.0
BOARD_NEAR_Z = 4.5     # nearest visible board edge (toward the camera)
BOARD_FAR_Z = -18.0    # far vanishing edge
HIT_Z = 3.5            # world Z where a note is "hit" (current time)
UNITS_PER_MS = 0.01    # track units per millisecond of look-ahead
NOTE_DEPTH = 0.55      # Z length of a tap-note tile

_EYE = (0.0, 7.0, 11.0)
_LOOK_AT = (0.0, 0.0, -3.0)
_FOV_Y = 50.0

# --- colors (RGBA, 0..1) ---------------------------------------------------
_BG = (0.015, 0.03, 0.07, 1.0)
_BOARD = (0.03, 0.05, 0.10, 1.0)
_LANE_TINT = (1.0, 1.0, 1.0, 0.60)
_DIVIDER = (0.55, 0.78, 1.0, 0.5)
_CENTER_DIVIDER = (1.0, 0.30, 0.42, 0.85)
_HOLD_TINT = (1.0, 1.0, 1.0, 0.85)
_NOTE_TINT = (1.0, 1.0, 1.0, 1.0)
_NOTE_HIT = (0.35, 0.95, 0.65, 1.0)
_NOTE_MISS = (0.42, 0.20, 0.28, 0.7)


def _lane_family(lane: int, lane_count: int) -> str:
    """Atlas color family for a lane (mirrors the 2D renderer's lane coloring)."""
    if lane_count % 2 == 1 and lane == lane_count // 2:
        return 'red'
    return 'blue' if lane % 2 == 0 else 'white'


class Renderer:
    """Draws one frame of the 3D playfield to the current GL window."""

    def __init__(self, size: tuple[int, int]) -> None:
        self.width, self.height = size
        self._atlas = AtlasTexture()

    def render(self, chart: Chart, current_ms: float) -> None:
        """Draw the playfield for *chart* at scroll position *current_ms*."""
        glViewport(0, 0, self.width, self.height)
        glClearColor(*_BG)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self._setup_camera()

        # Coplanar neon, composited back-to-front (painter's order); depth test
        # off so stacked translucent quads blend cleanly without z-fighting.
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self._draw_board()
        self._draw_lanes(chart.lane_count)
        self._draw_hit_bar()
        self._draw_notes(chart, current_ms)

    # --- camera ------------------------------------------------------------

    def _setup_camera(self) -> None:
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(_FOV_Y, self.width / self.height, 0.1, 80.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        gluLookAt(*_EYE, *_LOOK_AT, 0.0, 1.0, 0.0)

    # --- scene -------------------------------------------------------------

    def _draw_board(self) -> None:
        glColor4f(*_BOARD)
        glBegin(GL_QUADS)
        for v in _flat_quad(BOARD_LEFT, BOARD_RIGHT, BOARD_FAR_Z, BOARD_NEAR_Z):
            glVertex3f(*v)
        glEnd()

    def _draw_lanes(self, lane_count: int) -> None:
        for lane in range(lane_count):
            left, right = geometry.lane_bounds_world(lane, lane_count,
                                                     BOARD_LEFT, BOARD_RIGHT)
            family = _lane_family(lane, lane_count)
            self._textured_quad(
                _flat_quad(left, right, BOARD_FAR_Z, BOARD_NEAR_Z, y=0.01),
                self._atlas.uv(family, 'lane'), _LANE_TINT)

        # Lane dividers.
        glLineWidth(1.5)
        glBegin(GL_LINES)
        for i in range(lane_count + 1):
            x = BOARD_LEFT + (BOARD_RIGHT - BOARD_LEFT) * i / lane_count
            center = lane_count % 2 == 1 and i in (lane_count // 2, lane_count // 2 + 1)
            glColor4f(*(_CENTER_DIVIDER if center else _DIVIDER))
            glVertex3f(x, 0.02, BOARD_FAR_Z)
            glVertex3f(x, 0.02, BOARD_NEAR_Z)
        glEnd()

    def _draw_hit_bar(self) -> None:
        self._textured_quad(
            _flat_quad(BOARD_LEFT, BOARD_RIGHT, HIT_Z - 0.3, HIT_Z + 0.3, y=0.03),
            self._atlas.uv('blue', 'hit'), _NOTE_TINT)

    def _draw_notes(self, chart: Chart, current_ms: float) -> None:
        for note in chart.notes:
            head_z = HIT_Z - geometry.note_z(note.time_ms, current_ms, UNITS_PER_MS)
            left, right = geometry.lane_bounds_world(note.lane, chart.lane_count,
                                                     BOARD_LEFT, BOARD_RIGHT)
            inset = (right - left) * 0.12
            left, right = left + inset, right - inset
            family = _lane_family(note.lane, chart.lane_count)

            if note.duration_ms > 0:
                tail_z = HIT_Z - geometry.note_z(note.time_ms + note.duration_ms,
                                                 current_ms, UNITS_PER_MS)
                span = geometry.clamp_interval(tail_z, head_z, BOARD_FAR_Z, BOARD_NEAR_Z)
                if span is not None:
                    lo, hi = span
                    self._textured_quad(
                        _flat_quad(left, right, lo, hi, y=0.04),
                        self._atlas.uv(family, 'hold'), _HOLD_TINT)

            near = head_z + NOTE_DEPTH / 2
            far = head_z - NOTE_DEPTH / 2
            if near < BOARD_FAR_Z or far > BOARD_NEAR_Z:
                continue  # fully off the board
            verts = _flat_quad(left, right, far, near, y=0.05)
            if note.hit:
                self._textured_quad(verts, None, _NOTE_HIT)
            elif note.missed:
                self._textured_quad(verts, None, _NOTE_MISS)
            else:
                self._textured_quad(verts, self._atlas.uv(family, 'note'), _NOTE_TINT)

    # --- primitive ---------------------------------------------------------

    def _textured_quad(self, verts, uv, tint) -> None:
        """Draw a 4-vertex quad textured with atlas region *uv* (or flat-tinted
        when uv is None or the atlas is unavailable). *tint* multiplies the
        sampled texels — the extensibility seam for later effects."""
        glColor4f(*tint)
        if uv is not None and self._atlas.available:
            glEnable(GL_TEXTURE_2D)
            self._atlas.bind()
            u0, v0, u1, v1 = uv
            glBegin(GL_QUADS)
            glTexCoord2f(u0, v0); glVertex3f(*verts[0])
            glTexCoord2f(u1, v0); glVertex3f(*verts[1])
            glTexCoord2f(u1, v1); glVertex3f(*verts[2])
            glTexCoord2f(u0, v1); glVertex3f(*verts[3])
            glEnd()
            glDisable(GL_TEXTURE_2D)
        else:
            glBegin(GL_QUADS)
            for v in verts:
                glVertex3f(*v)
            glEnd()


def _flat_quad(x_left: float, x_right: float, z_far: float, z_near: float,
               y: float = 0.0):
    """Four corners of a quad lying on the y-plane, ordered far-left, far-right,
    near-right, near-left (matches atlas UV corner order)."""
    return [(x_left, y, z_far), (x_right, y, z_far),
            (x_right, y, z_near), (x_left, y, z_near)]
