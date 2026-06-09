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
    GL_LINES, GL_MODELVIEW, GL_ONE, GL_ONE_MINUS_SRC_ALPHA, GL_PROJECTION, GL_QUADS,
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
_LANE_WHITE = (0.035, 0.045, 0.065, 0.52)  # dark glass, not a white floor stripe
_LANE_BLACK = (0.015, 0.050, 0.110, 0.56)  # faint blue tint for black keys
_LANE_RED = (0.090, 0.018, 0.030, 0.50)    # subtle PC center-lane tint
_DIVIDER_GLOW = (0.05, 0.38, 1.00, 0.22)
_DIVIDER_CORE = (0.78, 0.88, 1.00, 0.64)
_LANE_FILL = {'white': _LANE_WHITE, 'blue': _LANE_BLACK, 'red': _LANE_RED}
_HOLD_TINT = (1.0, 1.0, 1.0, 0.85)
_NOTE_TINT = (1.0, 1.0, 1.0, 1.0)
_NOTE_HIT = (0.35, 0.95, 0.65, 1.0)
_NOTE_MISS = (0.42, 0.20, 0.28, 0.7)
_FX_TINT = {
    'blue': (0.08, 0.48, 1.0),
    'white': (0.90, 0.95, 1.0),
    'red': (1.0, 0.10, 0.18),
}

# MIDI pitch classes of the black keys (C#, D#, F#, G#, A#).
_BLACK_KEYS = frozenset({1, 3, 6, 8, 10})


def is_black_key(note: int) -> bool:
    """Whether a MIDI note is a black (accidental) piano key."""
    return note % 12 in _BLACK_KEYS


def lane_overlay_alpha(lane_count: int) -> float:
    """Alpha for the lane atlas texture drawn over the flat lane color.

    Extremely subtle by design: the atlas lane sprites are opaque blue/white/red,
    so they are used only as a low-alpha detail wash over a dark glass lane.
    At large MIDI lane counts the texture fades further to protect readability."""
    if lane_count <= 12:
        return 0.055
    if lane_count <= 25:
        return 0.035
    return 0.018


def lane_family(lane: int, mode: str, midi_low: int, lane_count: int) -> str:
    """Atlas color family for a lane. In 1:1 'midi' mode each lane is a piano
    key: white keys -> 'white', black keys -> 'blue' (so the board reads like a
    keyboard), never red. In compressed 'pc' mode lanes don't map to keys, so
    alternate white/blue with the center (space-bar) lane highlighted 'red'."""
    if mode == 'midi':
        return 'blue' if is_black_key(midi_low + lane) else 'white'
    if lane_count % 2 == 1 and lane == lane_count // 2:
        return 'red'
    return 'blue' if lane % 2 == 0 else 'white'


class Renderer:
    """Draws one frame of the 3D playfield to the current GL window."""

    def __init__(self, size: tuple[int, int]) -> None:
        self.width, self.height = size
        self._atlas = AtlasTexture()

    def render(self, chart: Chart, current_ms: float,
               sparks: list[tuple[int, float]] | None = None) -> None:
        """Draw the playfield for *chart* at scroll position *current_ms*.

        *sparks* is an optional list of (lane, intensity) hit flashes from
        ScoringEngine.recent_hits, drawn as impact blooms over the hit bar."""
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
        self._draw_lanes(chart)
        self._draw_hit_bar()
        self._draw_notes(chart, current_ms)
        if sparks:
            self._draw_sparks(chart, sparks)

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

    def _draw_lanes(self, chart: Chart) -> None:
        lane_count = chart.lane_count
        midi_low = chart.kb_class.midi_low
        overlay_alpha = lane_overlay_alpha(lane_count)
        overlay_tint = (1.0, 1.0, 1.0, overlay_alpha)
        for lane in range(lane_count):
            left, right = geometry.lane_bounds_world(lane, lane_count,
                                                     BOARD_LEFT, BOARD_RIGHT)
            # Two passes: a flat key color for clarity, then the lane atlas
            # texture at very low alpha for arcade detail. MIDI: natural keys
            # are dark neutral, black keys carry a faint blue tint. PC keeps the
            # red center-lane identity without turning the highway into colored
            # floor stripes.
            family = lane_family(lane, chart.mode, midi_low, lane_count)
            self._textured_quad(
                _flat_quad(left, right, BOARD_FAR_Z, BOARD_NEAR_Z, y=0.01),
                None, _LANE_FILL[family])
            if self._atlas.available:
                self._textured_quad(
                    _flat_quad(left, right, BOARD_FAR_Z, BOARD_NEAR_Z, y=0.011),
                    self._atlas.uv(family, 'lane'), overlay_tint)

        # Lane dividers: soft blue bloom underneath, crisp pale core on top.
        for width, color, y in ((5.0, _DIVIDER_GLOW, 0.022),
                                (1.4, _DIVIDER_CORE, 0.024)):
            glLineWidth(width)
            glColor4f(*color)
            glBegin(GL_LINES)
            for i in range(lane_count + 1):
                x = BOARD_LEFT + (BOARD_RIGHT - BOARD_LEFT) * i / lane_count
                glVertex3f(x, y, BOARD_FAR_Z)
                glVertex3f(x, y, BOARD_NEAR_Z)
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
            family = lane_family(note.lane, chart.mode, chart.kb_class.midi_low,
                                 chart.lane_count)

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

    def _draw_sparks(self, chart: Chart, sparks: list[tuple[int, float]]) -> None:
        """Draw impact blooms at the hit bar for each (lane, intensity) flash."""
        lane_count = chart.lane_count
        midi_low = chart.kb_class.midi_low
        lane_w = (BOARD_RIGHT - BOARD_LEFT) / lane_count
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        for lane, intensity in sparks:
            intensity = max(0.0, min(1.0, intensity))
            if intensity <= 0.0:
                continue
            cx = geometry.lane_world_x(lane, lane_count, BOARD_LEFT, BOARD_RIGHT)
            family = lane_family(lane, chart.mode, midi_low, lane_count)
            color = _FX_TINT[family]
            pop = intensity ** 0.55
            lane_left, lane_right = geometry.lane_bounds_world(
                lane, lane_count, BOARD_LEFT, BOARD_RIGHT)

            # Lane-local shock lines make the hit read even when the atlas
            # spark lands between bright note/hold art, without leaving a
            # rectangular translucent slab behind.
            z_far = HIT_Z - 1.65 - 0.65 * pop
            z_near = HIT_Z + 0.52
            self._draw_fx_line((cx, 0.064, z_far), (cx, 0.064, z_near),
                               color, 0.50 * pop, 9.0)
            self._draw_fx_line((lane_left, 0.063, z_far), (lane_left, 0.063, z_near),
                               color, 0.25 * pop, 3.0)
            self._draw_fx_line((lane_right, 0.063, z_far), (lane_right, 0.063, z_near),
                               color, 0.25 * pop, 3.0)
            self._draw_fx_line((cx - lane_w * 1.9, 0.068, HIT_Z),
                               (cx + lane_w * 1.9, 0.068, HIT_Z),
                               color, 0.58 * pop, 13.0)
            self._draw_fx_line((cx - lane_w * 1.4, 0.069, HIT_Z + 0.02),
                               (cx + lane_w * 1.4, 0.069, HIT_Z + 0.02),
                               (1.0, 1.0, 1.0), 0.28 * pop, 4.0)

            half = max(lane_w * (1.25 + 0.45 * pop), 0.56)
            self._textured_quad(
                _flat_quad(cx - half, cx + half, HIT_Z - half, HIT_Z + half, y=0.070),
                self._atlas.uv(family, 'impact_spark'), (1.0, 1.0, 1.0, pop))
            self._draw_fx_line((cx - lane_w * 0.34, 0.075, HIT_Z),
                               (cx + lane_w * 0.34, 0.075, HIT_Z),
                               (1.0, 1.0, 1.0), 0.62 * pop, 7.0)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    @staticmethod
    def _draw_fx_line(start, end, color, alpha: float, width: float) -> None:
        glLineWidth(width)
        glColor4f(color[0], color[1], color[2], alpha)
        glBegin(GL_LINES)
        glVertex3f(*start)
        glVertex3f(*end)
        glEnd()

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
