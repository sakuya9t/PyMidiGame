"""
src/midi/classifier.py — Keyboard size classifier.

Determines the minimum standard keyboard size that covers the full note range
present in a list of NoteEvent objects.

Standard keyboard sizes (smallest to largest):
  25key:  48–72  (C3–C5,  2 octaves)
  32key:  41–72  (F2–C5,  2.5 octaves)
  37key:  41–77  (F2–F5,  3+ octaves)
  49key:  36–84  (C2–C6,  4 octaves)
  61key:  36–96  (C2–C7,  5 octaves)
  88key:  21–108 (A0–C8,  full piano)
"""
from __future__ import annotations

from dataclasses import dataclass

from src.midi.parser import NoteEvent


@dataclass
class KeyboardClass:
    """Describes a standard keyboard size and its MIDI note range."""
    name: str        # e.g. "25key", "49key"
    key_count: int   # Number of physical keys
    midi_low: int    # Lowest MIDI note this keyboard covers
    midi_high: int   # Highest MIDI note this keyboard covers
    lane_count: int  # == key_count in MIDI mode


# Table ordered smallest → largest; classify() returns the first fit.
_KEYBOARD_CLASSES: list[KeyboardClass] = [
    KeyboardClass(name='25key', key_count=25,  midi_low=48, midi_high=72,  lane_count=25),
    KeyboardClass(name='32key', key_count=32,  midi_low=41, midi_high=72,  lane_count=32),
    KeyboardClass(name='37key', key_count=37,  midi_low=41, midi_high=77,  lane_count=37),
    KeyboardClass(name='49key', key_count=49,  midi_low=36, midi_high=84,  lane_count=49),
    KeyboardClass(name='61key', key_count=61,  midi_low=36, midi_high=96,  lane_count=61),
    KeyboardClass(name='88key', key_count=88,  midi_low=21, midi_high=108, lane_count=88),
]


def classify(notes: list[NoteEvent]) -> KeyboardClass:
    """Return the smallest KeyboardClass whose range covers all notes.

    If the note list is empty, returns the smallest class (25key).
    If no class fits, returns 88key as a fallback.
    """
    if not notes:
        return _KEYBOARD_CLASSES[0]

    min_note = min(e.note for e in notes)
    max_note = max(e.note for e in notes)

    for kb_class in _KEYBOARD_CLASSES:
        if kb_class.midi_low <= min_note and max_note <= kb_class.midi_high:
            return kb_class

    # Fallback: no standard class covers the range
    return _KEYBOARD_CLASSES[-1]
