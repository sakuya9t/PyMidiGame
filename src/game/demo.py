"""
src/game/demo.py — Demo player.

Generates perfect InputSignals on behalf of the player, producing a flawless
100% run used when no MIDI device is connected. Satisfies the engine's
`DemoSource` Protocol (`tick`). See DESIGN.md §7.

Each note becomes a single press at its exact `time_ms`; forwarded through the
engine to `ScoringEngine.register_hit`, that lands dead-center in the PERFECT
window. Hold-note release signalling is deferred (InputSignal has no release
type, DESIGN.md §6), so a hold emits only its press.
"""
from __future__ import annotations

from src.game.chart import Chart
from src.input.signal import InputSignal


class DemoPlayer:
    """Pops a chart's notes as InputSignals as the clock reaches each one."""

    def __init__(self, chart: Chart) -> None:
        # Pending notes sorted by time so each tick yields them in order.
        self._pending = sorted(chart.notes, key=lambda n: n.time_ms)

    def tick(self, current_ms: float) -> list[InputSignal]:
        """Return a signal for every note whose time has arrived (popped once)."""
        due: list[InputSignal] = []
        i = 0
        for n in self._pending:
            if n.time_ms <= current_ms:
                due.append(InputSignal(lane=n.lane, time_ms=n.time_ms))
                i += 1
            else:
                break  # pending is sorted; nothing later is due yet
        if i:
            self._pending = self._pending[i:]
        return due
