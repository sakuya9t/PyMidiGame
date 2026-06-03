"""
src/input/signal.py — InputSignal.

The shared currency between input/demo producers (PC keyboard handler, MIDI
input adapter, DemoPlayer) and the game engine: "hit lane L at chart-clock
time T". The hold-note release type (DESIGN.md deferred issue §6) is out of
scope; a signal is a single press.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InputSignal:
    """A single player (or demo) input: hit lane at chart-clock time (ms)."""
    lane: int
    time_ms: float
