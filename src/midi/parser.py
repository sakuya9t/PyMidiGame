"""
src/midi/parser.py — MIDI file parser.

Reads a .mid file and produces a flat, time-absolute list of NoteEvent objects.
Handles MIDI type 0 (single track), type 1 (multi-track sync), and type 2
(multi-track async, treated like type 1).

Tempo map changes mid-file are applied correctly so all times are in
wall-clock milliseconds from the start of the song.
"""
from __future__ import annotations

from dataclasses import dataclass

import mido


@dataclass
class NoteEvent:
    """A single MIDI note with absolute time and duration in milliseconds."""
    note: int          # MIDI note number (0–127)
    time_ms: float     # Absolute start time in milliseconds
    duration_ms: float # Note duration in milliseconds
    channel: int       # MIDI channel (0–15)
    velocity: int      # 0–127 (velocity-0 notes are never emitted)


class MidiParser:
    """Parses a MIDI file into a sorted flat list of NoteEvent objects."""

    @staticmethod
    def parse(path: str) -> list[NoteEvent]:
        """Read *path* and return a list of NoteEvent sorted by time_ms.

        Algorithm:
        1. Build a unified tempo map from set_tempo meta messages across all
           tracks (tracks share the same tempo timeline in type 0/1 files).
        2. For each track, walk messages accumulating absolute ticks, record
           note_on (velocity > 0) open times, and close them on note_off or
           note_on with velocity == 0.
        3. Convert tick timestamps to milliseconds using the tempo map.
        4. Emit only NoteEvents whose velocity > 0.
        """
        mid = mido.MidiFile(path)
        ticks_per_beat = mid.ticks_per_beat

        # --- Build tempo map (list of (abs_tick, tempo_µs)) ---
        tempo_map: list[tuple[int, int]] = []
        for track in mid.tracks:
            abs_tick = 0
            for msg in track:
                abs_tick += msg.time
                if isinstance(msg, mido.MetaMessage) and msg.type == 'set_tempo':
                    tempo_map.append((abs_tick, msg.tempo))

        # Sort by tick; if no tempo found default to 120 BPM
        tempo_map.sort(key=lambda x: x[0])
        if not tempo_map or tempo_map[0][0] != 0:
            tempo_map.insert(0, (0, 500_000))  # 120 BPM default

        def ticks_to_ms(abs_tick: int) -> float:
            """Convert absolute tick position to milliseconds using the tempo map."""
            ms = 0.0
            prev_tick = 0
            current_tempo = tempo_map[0][1]

            for i, (change_tick, new_tempo) in enumerate(tempo_map):
                if abs_tick <= change_tick:
                    break
                # Accumulate time from prev_tick to min(change_tick, abs_tick)
                segment_end = min(change_tick, abs_tick)
                ms += (segment_end - prev_tick) * current_tempo / ticks_per_beat / 1000.0
                prev_tick = change_tick
                current_tempo = new_tempo
            else:
                # abs_tick is beyond the last tempo change
                pass

            # Remaining ticks after last processed segment
            if abs_tick > prev_tick:
                ms += (abs_tick - prev_tick) * current_tempo / ticks_per_beat / 1000.0

            return ms

        # --- Parse note events from all tracks ---
        raw_events: list[NoteEvent] = []

        for track in mid.tracks:
            abs_tick = 0
            # Maps (channel, note) -> (start_tick, velocity)
            open_notes: dict[tuple[int, int], tuple[int, int]] = {}

            for msg in track:
                abs_tick += msg.time

                if isinstance(msg, mido.MetaMessage):
                    continue

                if msg.type not in ('note_on', 'note_off'):
                    continue

                is_note_on  = msg.type == 'note_on'  and msg.velocity > 0
                is_note_off = msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0)

                key = (msg.channel, msg.note)

                if is_note_on:
                    open_notes[key] = (abs_tick, msg.velocity)
                elif is_note_off and key in open_notes:
                    start_tick, velocity = open_notes.pop(key)
                    raw_events.append(NoteEvent(
                        note=msg.note,
                        time_ms=ticks_to_ms(start_tick),
                        duration_ms=ticks_to_ms(abs_tick) - ticks_to_ms(start_tick),
                        channel=msg.channel,
                        velocity=velocity,
                    ))

        raw_events.sort(key=lambda e: e.time_ms)
        return raw_events
