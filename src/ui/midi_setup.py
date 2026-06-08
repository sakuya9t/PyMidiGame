"""
src/ui/midi_setup.py — MIDI device selection + calibration screen.

A small state machine:

    SELECT_DEVICE -> CALIBRATE_LOW -> CALIBRATE_HIGH -> DONE

Selecting a port opens it (the App handles the OpenDevice action); the player
then presses their lowest and highest keys. That both confirms the connection
(the presses echo live) and measures the playable span, since a MIDI port can't
report its key count. On DONE, Enter emits MidiConfigured(port, min, max).

Logic (handle_key / handle_midi) is pygame/OpenGL-free apart from key constants,
so it is unit-testable; render() draws the current step onto a surface (presented
over GL by the App, like the menu).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from src.midi.device import guess_key_count

_NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')

# Colors
_BG = (5, 8, 18)
_EDGE = (30, 175, 255)
_TEXT = (235, 245, 255)
_MUTED = (120, 170, 220)
_HILITE = (255, 205, 80)
_OK = (90, 240, 170)
_SEL_ROW = (24, 44, 80)


def note_name(note: int) -> str:
    """MIDI note number -> name like 'C4' (MIDI 60 = C4)."""
    return f"{_NOTE_NAMES[note % 12]}{note // 12 - 1}"


class SetupStep(Enum):
    SELECT_DEVICE = auto()
    CALIBRATE_LOW = auto()
    CALIBRATE_HIGH = auto()
    DONE = auto()


@dataclass
class OpenDevice:
    """Action: the App should open MIDI input port *index*."""
    index: int


@dataclass
class MidiConfigured:
    """Action: calibration complete — save this device + measured span."""
    index: int
    name: str
    min_note: int
    max_note: int


class CancelSetup:
    """Action: leave setup without saving."""


class MidiSetup:
    """Device-selection + calibration state machine and screen."""

    def __init__(self, ports: list[str], size: tuple[int, int]) -> None:
        self.ports = ports
        self.width, self.height = size
        self.step = SetupStep.SELECT_DEVICE
        self.selected = 0
        self.min_note: int | None = None
        self.max_note: int | None = None
        self.last_note: int | None = None
        pygame.font.init()
        self._title = pygame.font.SysFont('consolas,menlo,monospace', 40, bold=True)
        self._row = pygame.font.SysFont('consolas,menlo,monospace', 26)
        self._big = pygame.font.SysFont('consolas,menlo,monospace', 56, bold=True)
        self._hint = pygame.font.SysFont('consolas,menlo,monospace', 20)

    # --- logic -------------------------------------------------------------

    def handle_key(self, event):
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_ESCAPE:
            return CancelSetup

        if self.step is SetupStep.SELECT_DEVICE:
            if event.key == pygame.K_UP:
                self.selected = max(0, self.selected - 1)
            elif event.key == pygame.K_DOWN:
                self.selected = min(len(self.ports) - 1, self.selected + 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.ports:
                self._begin_calibration()
                return OpenDevice(self.selected)
            return None

        if self.step is SetupStep.DONE:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return MidiConfigured(self.selected, self.ports[self.selected],
                                      self.min_note, self.max_note)
            if event.key == pygame.K_r:
                self._begin_calibration()
            return None

        return None  # CALIBRATE_LOW / CALIBRATE_HIGH: only MIDI advances

    def handle_midi(self, msgs) -> None:
        for msg in msgs:
            if msg.kind != 'note_on':
                continue
            self.last_note = msg.note
            if self.step is SetupStep.CALIBRATE_LOW:
                self.min_note = msg.note
                self.step = SetupStep.CALIBRATE_HIGH
            elif self.step is SetupStep.CALIBRATE_HIGH:
                lo, hi = sorted((self.min_note, msg.note))
                if hi > lo:  # two distinct keys define the span
                    self.min_note, self.max_note = lo, hi
                    self.step = SetupStep.DONE

    @property
    def key_count(self) -> int | None:
        if self.min_note is None or self.max_note is None:
            return None
        return self.max_note - self.min_note + 1

    def _begin_calibration(self) -> None:
        self.step = SetupStep.CALIBRATE_LOW
        self.min_note = self.max_note = self.last_note = None

    # --- render ------------------------------------------------------------

    def render(self, target: pygame.Surface) -> None:
        target.fill(_BG)
        target.blit(self._title.render('MIDI SETUP', True, _EDGE), (60, 48))
        if self.step is SetupStep.SELECT_DEVICE:
            self._render_select(target)
        elif self.step in (SetupStep.CALIBRATE_LOW, SetupStep.CALIBRATE_HIGH):
            self._render_calibrate(target)
        else:
            self._render_done(target)

    def _render_select(self, target: pygame.Surface) -> None:
        target.blit(self._hint.render('SELECT INPUT DEVICE', True, _MUTED), (62, 110))
        if not self.ports:
            target.blit(self._row.render('No MIDI input ports found.', True, _MUTED),
                        (60, 170))
        for i, name in enumerate(self.ports):
            y = 160 + i * 44
            if i == self.selected:
                pygame.draw.rect(target, _SEL_ROW, pygame.Rect(40, y - 4, self.width - 80, 40))
                pygame.draw.rect(target, _EDGE, pygame.Rect(40, y - 4, 6, 40))
            color = _TEXT if i == self.selected else _MUTED
            target.blit(self._row.render(name, True, color), (60, y))
            hint = guess_key_count(name)
            if hint:
                tag = self._hint.render(f'~{hint} keys?', True, _MUTED)
                target.blit(tag, (self.width - tag.get_width() - 60, y + 4))
        self._footer(target, '↑↓ select    Enter choose    Esc cancel')

    def _render_calibrate(self, target: pygame.Surface) -> None:
        if self.step is SetupStep.CALIBRATE_LOW:
            prompt = 'Press your LOWEST key'
        else:
            prompt = 'Press your HIGHEST key'
        surf = self._big.render(prompt, True, _HILITE)
        target.blit(surf, surf.get_rect(center=(self.width // 2, 280)))

        if self.step is SetupStep.CALIBRATE_HIGH and self.min_note is not None:
            low = self._row.render(f'lowest: {note_name(self.min_note)} '
                                   f'({self.min_note})', True, _OK)
            target.blit(low, low.get_rect(center=(self.width // 2, 360)))

        if self.last_note is not None:
            echo = self._row.render(
                f'✓ received {note_name(self.last_note)} ({self.last_note})',
                True, _OK)
            target.blit(echo, echo.get_rect(center=(self.width // 2, 430)))

        self._footer(target, 'Esc cancel')

    def _render_done(self, target: pygame.Surface) -> None:
        text = (f'Detected {self.key_count} keys: '
                f'{note_name(self.min_note)} – {note_name(self.max_note)}')
        surf = self._big.render(text, True, _OK)
        target.blit(surf, surf.get_rect(center=(self.width // 2, 300)))
        self._footer(target, 'Enter save    R redo    Esc cancel')

    def _footer(self, target: pygame.Surface, text: str) -> None:
        surf = self._hint.render(text, True, _MUTED)
        target.blit(surf, surf.get_rect(center=(self.width // 2, self.height - 40)))
