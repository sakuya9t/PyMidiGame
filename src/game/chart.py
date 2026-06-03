"""
src/game/chart.py — Chart builder.

Converts a parsed list[NoteEvent] (from MidiParser.parse) plus a KeyboardClass
(from classify) into a sorted Chart that the rendering and scoring systems
consume. This is the last stage of the MIDI ingestion pipeline before gameplay.

Two lane-assignment modes:
  "midi" — 1:1 mapping; lane = note - kb_class.midi_low (lane_count = key_count).
  "pc"   — song pitch range compressed onto 8 lanes by linear interpolation,
           matching the 8-key PC layout [A S D F J K L ;].

See ai-working-log/specs/2026-05-04-chart-builder-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.midi.classifier import KeyboardClass
from src.midi.parser import NoteEvent

# Number of lanes in PC mode (matches PC_KEY_MAP = [A S D F J K L ;]).
PC_LANE_COUNT = 8


@dataclass
class Note:
    """A single playable note in chart coordinates."""
    lane: int            # 0-indexed lane within the chart's lane_count
    midi_note: int       # Original MIDI pitch (preserved for hold/release matching)
    time_ms: float       # Absolute hit time in milliseconds (chart clock)
    duration_ms: float   # Hold duration; 0.0 for tap notes
    hit: bool = False
    missed: bool = False


@dataclass
class Chart:
    """A complete playable chart."""
    notes: list[Note]          # Non-decreasing by time_ms; chord notes adjacent
    kb_class: KeyboardClass
    mode: str                  # "midi" or "pc"
    lane_count: int            # kb_class.key_count for "midi"; 8 for "pc"
    total_duration_ms: float   # max(time_ms + duration_ms); 0.0 if empty


class ChartBuilder:
    """Builds a Chart from parsed NoteEvents and a KeyboardClass."""

    @classmethod
    def build(cls, events: list[NoteEvent], kb_class: KeyboardClass,
              mode: str) -> Chart:
        """Convert *events* into a sorted Chart using the given lane *mode*.

        Args:
            events: parsed notes from MidiParser.parse (any order).
            kb_class: keyboard class from classify; declares the supported range.
            mode: "midi" (1:1) or "pc" (8 compressed lanes).

        Raises:
            ValueError: if *mode* is unknown, or any event note falls outside
                the kb_class range [midi_low, midi_high].
        """
        if mode not in ("midi", "pc"):
            raise ValueError(f"unknown mode {mode!r}; expected 'midi' or 'pc'")

        # kb_class declares the supported MIDI range. Any event outside it is a
        # contract violation. The classifier rejects these upstream; we enforce
        # the contract defensively here regardless of mode.
        for e in events:
            if not (kb_class.midi_low <= e.note <= kb_class.midi_high):
                raise ValueError(
                    f"MIDI note {e.note} is outside the {kb_class.name} range "
                    f"[{kb_class.midi_low}, {kb_class.midi_high}]"
                )

        lane_count = kb_class.key_count if mode == "midi" else PC_LANE_COUNT

        if not events:
            return Chart(notes=[], kb_class=kb_class, mode=mode,
                         lane_count=lane_count, total_duration_ms=0.0)

        if mode == "midi":
            notes = [
                Note(lane=e.note - kb_class.midi_low, midi_note=e.note,
                     time_ms=e.time_ms, duration_ms=e.duration_ms)
                for e in events
            ]
        else:  # mode == "pc"
            notes = cls._assign_pc_lanes(events, lane_count)

        # Stable sort keeps chord notes (identical time_ms) in input order.
        notes.sort(key=lambda n: n.time_ms)
        total = max(n.time_ms + n.duration_ms for n in notes)
        return Chart(notes=notes, kb_class=kb_class, mode=mode,
                     lane_count=lane_count, total_duration_ms=total)

    @staticmethod
    def _assign_pc_lanes(events: list[NoteEvent], lane_count: int) -> list[Note]:
        """Map the song's pitch range onto *lane_count* lanes by interpolation.

        song_min anchors at lane 0, song_max at lane lane_count-1; intermediate
        pitches fall on a uniform scale. A single-pitch song collapses to lane 0.

        Rounding uses half-up int(x + 0.5) rather than round(), whose banker's
        rounding would systematically skip odd lanes when (offset/span) lands
        exactly on .5.
        """
        song_min = min(e.note for e in events)
        song_max = max(e.note for e in events)

        if song_min == song_max:
            return [
                Note(lane=0, midi_note=e.note,
                     time_ms=e.time_ms, duration_ms=e.duration_ms)
                for e in events
            ]

        span = song_max - song_min
        return [
            Note(lane=int((e.note - song_min) / span * (lane_count - 1) + 0.5),
                 midi_note=e.note,
                 time_ms=e.time_ms, duration_ms=e.duration_ms)
            for e in events
        ]
