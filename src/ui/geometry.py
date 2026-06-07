"""
src/ui/geometry.py — pure world-space math for the GL perspective renderer.

Camera-agnostic and free of pygame/OpenGL: these functions place notes along the
track and lanes across the board, and clamp intervals (for note culling and the
hold-note length clamp). They form the headless-testable core of the renderer;
the GL renderer composes them with the camera and board constants.
"""
from __future__ import annotations


def note_z(time_ms: float, current_ms: float, units_per_ms: float) -> float:
    """Track offset of a note from the hit point. Future notes are positive
    (far ahead), a note at the current time is 0, past notes are negative."""
    return (time_ms - current_ms) * units_per_ms


def lane_world_x(lane: int, lane_count: int, left: float, right: float) -> float:
    """World X of the center of *lane* across the board span [left, right]."""
    lane_w = (right - left) / lane_count
    return left + (lane + 0.5) * lane_w


def lane_bounds_world(lane: int, lane_count: int, left: float,
                      right: float) -> tuple[float, float]:
    """World X of the left and right edges of *lane* across [left, right]."""
    lane_w = (right - left) / lane_count
    return left + lane * lane_w, left + (lane + 1) * lane_w


def clamp_interval(lo: float, hi: float, bound_lo: float,
                   bound_hi: float) -> tuple[float, float] | None:
    """Intersect [lo, hi] with [bound_lo, bound_hi]. Inputs may be reversed
    (normalized first). Returns the clamped (low, high) pair, or None if the
    interval lies entirely outside the bounds."""
    if lo > hi:
        lo, hi = hi, lo
    low = max(lo, bound_lo)
    high = min(hi, bound_hi)
    if low > high:
        return None
    return low, high
