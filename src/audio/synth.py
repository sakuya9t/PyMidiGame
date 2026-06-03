"""
src/audio/synth.py - lightweight MIDI preview synthesis.

This is a dependency-free fallback for the launcher when a chart has no paired
produced audio file. It renders chart notes to a temporary WAV so pygame.mixer
can play something audible even on systems where SDL_mixer cannot synthesize
MIDI files directly.
"""
from __future__ import annotations

import atexit
import math
import os
import tempfile
import wave
from array import array

from src.game.chart import Chart
from src.midi.parser import MidiParser

SAMPLE_RATE = 22_050
TAIL_MS = 500.0
MIN_NOTE_MS = 90.0
ATTACK_MS = 8.0
RELEASE_MS = 45.0
AMPLITUDE = 0.16

_TEMP_FILES: list[str] = []


def synthesize_midi_to_wav(midi_path: str, *, chart: Chart | None = None) -> str:
    """Render *midi_path* or an already-built *chart* into a temporary WAV file.

    The returned path is registered for best-effort cleanup at process exit.
    """
    notes = chart.notes if chart is not None else _notes_from_midi(midi_path)
    total_ms = _total_ms(notes)
    sample_count = max(1, int((total_ms + TAIL_MS) / 1000.0 * SAMPLE_RATE))
    mix = array('f', [0.0]) * sample_count

    for note in notes:
        _mix_note(mix, _pitch(note), note.time_ms, note.duration_ms)

    pcm = _float_mix_to_pcm(mix)
    path = _new_temp_path()
    with wave.open(path, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return path


def _notes_from_midi(midi_path: str):
    # Importing ChartBuilder here would force classification/lane decisions just
    # for sound; the synth only needs pitch and timing.
    return MidiParser.parse(midi_path)


def _total_ms(notes) -> float:
    if not notes:
        return 0.0
    return max(n.time_ms + max(n.duration_ms, MIN_NOTE_MS) for n in notes)


def _pitch(note) -> int:
    if hasattr(note, 'midi_note'):
        return note.midi_note
    return note.note


def _mix_note(mix: array, midi_note: int, start_ms: float, duration_ms: float) -> None:
    start = max(0, int(start_ms / 1000.0 * SAMPLE_RATE))
    duration = max(duration_ms, MIN_NOTE_MS)
    length = max(1, int(duration / 1000.0 * SAMPLE_RATE))
    end = min(len(mix), start + length)
    if start >= end:
        return

    freq = 440.0 * (2 ** ((midi_note - 69) / 12.0))
    attack = max(1, int(ATTACK_MS / 1000.0 * SAMPLE_RATE))
    release = max(1, int(RELEASE_MS / 1000.0 * SAMPLE_RATE))

    for sample_index in range(start, end):
        local = sample_index - start
        remaining = end - sample_index - 1
        env = min(1.0, local / attack, remaining / release)
        t = sample_index / SAMPLE_RATE
        # A little harmonic keeps the preview from sounding too sterile while
        # staying cheap and deterministic.
        value = math.sin(2.0 * math.pi * freq * t)
        value += 0.35 * math.sin(2.0 * math.pi * freq * 2.0 * t)
        mix[sample_index] += value * env * AMPLITUDE


def _float_mix_to_pcm(mix: array) -> array:
    max_abs = max((abs(v) for v in mix), default=0.0)
    scale = 0.95 / max_abs if max_abs > 0.95 else 1.0
    pcm = array('h')
    for sample in mix:
        clipped = max(-1.0, min(1.0, sample * scale))
        pcm.append(int(clipped * 32767))
    return pcm


def _new_temp_path() -> str:
    handle = tempfile.NamedTemporaryFile(
        prefix='midimania-preview-', suffix='.wav', delete=False
    )
    path = handle.name
    handle.close()
    _TEMP_FILES.append(path)
    return path


def _cleanup_temp_files() -> None:
    for path in _TEMP_FILES:
        try:
            os.remove(path)
        except OSError:
            pass


atexit.register(_cleanup_temp_files)
