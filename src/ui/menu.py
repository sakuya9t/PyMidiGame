"""
src/ui/menu.py — song library scanner + song selection screen.

`scan_songs` walks a `songs/` directory of per-song folders into displayable
`SongEntry` metadata (title, artist, classified keyboard size, duration). A
folder without a chart, or one whose MIDI won't parse, is skipped rather than
fatal, so one bad song can't break the menu.

`SongMenu` is the MENU screen: it owns selection/input-mode state, turns key
events into `StartGame`/`QuitGame` actions, and draws itself onto a pygame
surface (so it runs headlessly under SDL's dummy driver, like `Renderer`).

Real MIDI device input isn't built yet, so MIDI Keyboard is shown but disabled;
only PC Keyboard and Demo are selectable (see SELECTABLE_MODES).
"""
from __future__ import annotations

import os
import json
from dataclasses import dataclass

import pygame

from src.midi.parser import MidiParser
from src.midi.classifier import classify, classes_within, keyboard_class_by_name

# Produced-audio extensions accepted as a sibling of the chart, in preference
# order. Kept local (not imported from src.app) to avoid an import cycle.
_AUDIO_EXTS = ('.ogg', '.mp3', '.wav', '.flac')
_MIDI_EXTS = ('.mid', '.midi')

# Input modes the player can actually pick this build. "midi" is shown in the UI
# but disabled until real device input exists.
SELECTABLE_MODES = ('pc', 'demo')

_MODE_LABELS = {'pc': 'PC Keyboard', 'midi': 'MIDI Keyboard', 'demo': 'Demo'}
_DISPLAY_MODES = ('pc', 'midi', 'demo')  # left-to-right in the selector

# Colors
_BG = (5, 8, 18)
_PANEL = (12, 18, 32)
_EDGE = (30, 175, 255)
_TEXT = (235, 245, 255)
_MUTED = (120, 170, 220)
_DISABLED = (70, 80, 100)
_HILITE = (255, 205, 80)
_SEL_ROW = (24, 44, 80)
_OK = (90, 240, 170)
_CENTER = (255, 48, 70)


@dataclass
class SongEntry:
    """One scanned song, with all fields ready to display."""
    name: str                 # directory name (stable id)
    dir: str                  # path to the song folder
    midi_path: str            # chart .mid
    audio_path: str | None    # produced audio beside the MIDI, else None
    title: str                # meta.json title, else prettified dir name
    artist: str               # meta.json artist, else ""
    key_class: str            # classified keyboard size, e.g. "32key"
    total_duration_ms: float  # max(time_ms + duration_ms) across notes
    bpm: float | None         # meta.json bpm, else None (not derived from MIDI in v1)


@dataclass
class MidiConfig:
    """A configured MIDI input device and its calibrated playable span."""
    name: str
    min_note: int
    max_note: int


@dataclass
class StartGame:
    """Menu action: begin a run of *entry* in *input_mode* ('pc'/'demo'/'midi').

    keys_mode is 'auto' (classify per song) or a keyboard-class name (e.g.
    '49key') chosen for MIDI play."""
    entry: SongEntry
    input_mode: str
    keys_mode: str = 'auto'


class QuitGame:
    """Menu action: leave the game."""


class OpenMidiSetup:
    """Menu action: open the MIDI device setup/calibration screen."""


# --- scanning --------------------------------------------------------------

def _prettify(name: str) -> str:
    return name.replace('-', ' ').replace('_', ' ').title()


def _find_chart(song_dir: str) -> str | None:
    """Prefer chart.mid; else the first *.mid/*.midi by name. None if none."""
    entries = sorted(os.listdir(song_dir))
    if 'chart.mid' in entries:
        return os.path.join(song_dir, 'chart.mid')
    for name in entries:
        if os.path.splitext(name)[1].lower() in _MIDI_EXTS:
            return os.path.join(song_dir, name)
    return None


def _find_audio(midi_path: str) -> str | None:
    """A produced audio file sharing the chart's stem, else None."""
    stem, _ = os.path.splitext(midi_path)
    for ext in _AUDIO_EXTS:
        candidate = stem + ext
        if os.path.exists(candidate):
            return candidate
    return None


def _read_meta(song_dir: str) -> dict:
    path = os.path.join(song_dir, 'meta.json')
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _scan_one(song_dir: str, name: str) -> SongEntry | None:
    """Build a SongEntry for one folder, or None if it has no usable chart."""
    midi_path = _find_chart(song_dir)
    if midi_path is None:
        return None
    try:
        events = MidiParser.parse(midi_path)
        kb = classify(events)
    except Exception as exc:  # unparseable / out-of-range -> skip this song
        print(f"[MidiMania] skipping {name!r}: {exc}")
        return None

    total = max((e.time_ms + e.duration_ms for e in events), default=0.0)
    meta = _read_meta(song_dir)
    return SongEntry(
        name=name,
        dir=song_dir,
        midi_path=midi_path,
        audio_path=_find_audio(midi_path),
        title=meta.get('title') or _prettify(name),
        artist=meta.get('artist', ''),
        key_class=kb.name,
        total_duration_ms=total,
        bpm=meta.get('bpm'),
    )


def scan_songs(songs_dir: str) -> list[SongEntry]:
    """Scan *songs_dir* for per-song folders into a sorted list of SongEntry.

    A missing directory, folders without a chart, and folders whose MIDI won't
    parse all yield nothing (the scan never raises on bad content).
    """
    if not os.path.isdir(songs_dir):
        return []
    songs: list[SongEntry] = []
    for name in sorted(os.listdir(songs_dir)):
        song_dir = os.path.join(songs_dir, name)
        if not os.path.isdir(song_dir):
            continue
        entry = _scan_one(song_dir, name)
        if entry is not None:
            songs.append(entry)
    return songs


def _fmt_duration(ms: float) -> str:
    total_s = int(ms // 1000)
    return f"{total_s // 60}:{total_s % 60:02d}"


# --- the menu screen -------------------------------------------------------

class SongMenu:
    """The MENU screen: select a song + input mode, or quit."""

    def __init__(self, songs: list[SongEntry], size: tuple[int, int],
                 midi_config: MidiConfig | None = None) -> None:
        self.songs = songs
        self.width, self.height = size
        self.selected_index = 0
        self.mode_index = 0  # over selectable_modes
        self.keys_index = 0  # over keys_options
        self.midi_config = midi_config
        pygame.font.init()
        self._title = pygame.font.SysFont('consolas,menlo,monospace', 44, bold=True)
        self._row = pygame.font.SysFont('consolas,menlo,monospace', 26)
        self._small = pygame.font.SysFont('consolas,menlo,monospace', 18)
        self._hint = pygame.font.SysFont('consolas,menlo,monospace', 16)

    # --- selection state ---------------------------------------------------

    @property
    def selectable_modes(self) -> list[str]:
        """Input modes the player can pick now. MIDI appears once a device is
        configured (see set_midi_config)."""
        modes = list(SELECTABLE_MODES)
        if self.midi_config is not None:
            modes.append('midi')
        return modes

    @property
    def input_mode(self) -> str:
        modes = self.selectable_modes
        return modes[self.mode_index % len(modes)]

    @property
    def keys_options(self) -> list[str]:
        """'auto' plus the keyboard sizes that fit the configured device span."""
        if self.midi_config is None:
            return ['auto']
        fitting = classes_within(self.midi_config.min_note, self.midi_config.max_note)
        return ['auto'] + [c.name for c in fitting]

    @property
    def keys_mode(self) -> str:
        opts = self.keys_options
        return opts[self.keys_index % len(opts)]

    def set_midi_config(self, config: MidiConfig | None) -> None:
        """Apply a configured device, resetting mode/keys selection."""
        self.midi_config = config
        self.mode_index = 0
        self.keys_index = 0

    def midi_playable(self, song: SongEntry) -> bool:
        """Whether *song* can be played on the current device + keys-mode."""
        if self.midi_config is None:
            return False
        song_cls = keyboard_class_by_name(song.key_class)
        if song_cls is None:
            return False
        if self.keys_mode == 'auto':
            lo, hi = self.midi_config.min_note, self.midi_config.max_note
        else:
            chosen = keyboard_class_by_name(self.keys_mode)
            lo, hi = chosen.midi_low, chosen.midi_high
        return song_cls.midi_low >= lo and song_cls.midi_high <= hi

    # --- events ------------------------------------------------------------

    def handle_event(self, event) -> StartGame | QuitGame | OpenMidiSetup | None:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_ESCAPE:
            return QuitGame()
        if event.key == pygame.K_m:
            return OpenMidiSetup()
        if event.key == pygame.K_DOWN:
            self._move(1)
        elif event.key == pygame.K_UP:
            self._move(-1)
        elif event.key == pygame.K_RIGHT:
            self.mode_index = (self.mode_index + 1) % len(self.selectable_modes)
        elif event.key == pygame.K_LEFT:
            self.mode_index = (self.mode_index - 1) % len(self.selectable_modes)
        elif event.key == pygame.K_k:
            self.keys_index = (self.keys_index + 1) % len(self.keys_options)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.songs:
                song = self.songs[self.selected_index]
                if self.input_mode == 'midi' and not self.midi_playable(song):
                    return None  # song doesn't fit the device/keys; can't start
                return StartGame(song, self.input_mode, self.keys_mode)
        return None

    def _move(self, delta: int) -> None:
        if not self.songs:
            return
        self.selected_index = max(0, min(len(self.songs) - 1,
                                         self.selected_index + delta))

    # --- rendering ---------------------------------------------------------

    def render(self, target: pygame.Surface) -> None:
        target.fill(_BG)
        target.blit(self._title.render('MIDIMANIA', True, _EDGE), (60, 40))
        target.blit(self._small.render('SELECT SONG', True, _MUTED), (64, 96))

        if self.songs:
            self._draw_list(target)
            self._draw_detail(target)
        else:
            self._draw_empty(target)

        self._draw_mode_selector(target)
        self._draw_keys_and_device(target)
        self._draw_hints(target)

    def _draw_list(self, target: pygame.Surface) -> None:
        x, top, row_h = 60, 150, 44
        for i, song in enumerate(self.songs):
            y = top + i * row_h
            if y > self.height - 200:
                break
            if i == self.selected_index:
                pygame.draw.rect(target, _SEL_ROW,
                                 pygame.Rect(x - 12, y - 4, self.width - 96, row_h - 6))
                pygame.draw.rect(target, _EDGE,
                                 pygame.Rect(x - 12, y - 4, 4, row_h - 6))
            color = _TEXT if i == self.selected_index else _MUTED
            target.blit(self._row.render(song.title, True, color), (x, y))
            meta = f"{song.key_class}  {_fmt_duration(song.total_duration_ms)}"
            surf = self._small.render(meta, True, _MUTED)
            target.blit(surf, (self.width - 96 - surf.get_width(), y + 4))

    def _draw_detail(self, target: pygame.Surface) -> None:
        song = self.songs[self.selected_index]
        y = self.height - 200
        parts = [song.title]
        if song.artist:
            parts.append(song.artist)
        parts.append(song.key_class)
        if song.bpm:
            parts.append(f"{int(song.bpm)} BPM")
        parts.append(_fmt_duration(song.total_duration_ms))
        surf = self._small.render('   '.join(parts), True, _MUTED)
        target.blit(surf, (60, y))
        if self.input_mode == 'midi':
            ok = self.midi_playable(song)
            tag = '  fits your keyboard' if ok else '  needs a larger keyboard'
            target.blit(self._small.render(tag, True, _OK if ok else _CENTER),
                        (60 + surf.get_width(), y))

    def _draw_empty(self, target: pygame.Surface) -> None:
        msg = 'No songs found — add a folder under songs/ with a chart.mid.'
        surf = self._row.render(msg, True, _MUTED)
        target.blit(surf, surf.get_rect(center=(self.width // 2, self.height // 2 - 40)))

    def _draw_mode_selector(self, target: pygame.Surface) -> None:
        y = self.height - 150
        target.blit(self._small.render('MODE', True, _MUTED), (60, y - 22))
        selectable = self.selectable_modes
        x = 60
        for mode in _DISPLAY_MODES:
            is_sel = mode in selectable
            label = _MODE_LABELS[mode]
            if mode == 'midi' and not is_sel:
                label += '  (no device)'
            active = is_sel and mode == self.input_mode
            color = _HILITE if active else (_TEXT if is_sel else _DISABLED)
            surf = self._row.render(label, True, color)
            rect = pygame.Rect(x - 8, y - 4, surf.get_width() + 16, surf.get_height() + 8)
            if active:
                pygame.draw.rect(target, _PANEL, rect)
                pygame.draw.rect(target, _HILITE, rect, 2)
            target.blit(surf, (x, y))
            x += surf.get_width() + 40

    def _draw_keys_and_device(self, target: pygame.Surface) -> None:
        y = self.height - 104
        target.blit(self._small.render('KEYS', True, _MUTED), (60, y - 20))
        x = 60
        for opt in self.keys_options:
            label = 'AUTO' if opt == 'auto' else opt
            active = opt == self.keys_mode
            surf = self._small.render(label, True, _HILITE if active else _TEXT)
            if active:
                pygame.draw.rect(target, _HILITE,
                                 pygame.Rect(x - 6, y - 3, surf.get_width() + 12,
                                             surf.get_height() + 6), 1)
            target.blit(surf, (x, y))
            x += surf.get_width() + 22

        dy = self.height - 70
        if self.midi_config is not None:
            span = self.midi_config.max_note - self.midi_config.min_note + 1
            text, color = (f'DEVICE: {self.midi_config.name}  ({span} keys)', _OK)
        else:
            text, color = ('DEVICE: none — press M to set up', _MUTED)
        target.blit(self._small.render(text, True, color), (60, dy))

    def _draw_hints(self, target: pygame.Surface) -> None:
        hint = ('↑↓ song   ←→ mode   K keys   M midi setup   Enter play   Esc quit')
        surf = self._hint.render(hint, True, _MUTED)
        target.blit(surf, (60, self.height - 40))
