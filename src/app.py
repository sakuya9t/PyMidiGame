"""
src/app.py — MidiMania application: wire the pipeline into a playable loop.

Assembles MidiParser -> classify -> ChartBuilder -> GameEngine (with
ScoringEngine, AudioPlayer clock, and optional DemoPlayer) -> Renderer, and
runs the pygame main loop.

The wiring (build_chart / make_engine / build_keymap) is separated from the
pygame loop so it can be driven headlessly in tests.
"""
from __future__ import annotations

import os
from typing import Callable

import pygame

from src.midi.parser import MidiParser
from src.midi.classifier import classify
from src.game.chart import Chart, ChartBuilder
from src.game.engine import GameEngine
from src.game.scoring import ScoringEngine
from src.game.demo import DemoPlayer
from src.audio.player import AudioPlayer
from src.audio.synth import synthesize_midi_to_wav
from src.ui.renderer import Renderer

SIZE = (960, 720)

# PC keyboard lane mapping for up to 8 lanes: A S D F J K L ;
PC_KEYS = [pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_f,
           pygame.K_j, pygame.K_k, pygame.K_l, pygame.K_SEMICOLON]


def build_chart(midi_path: str, mode: str = 'midi') -> Chart:
    """Parse, classify, and build a chart from a .mid file."""
    events = MidiParser.parse(midi_path)
    kb = classify(events)
    return ChartBuilder.build(events, kb, mode)


def make_engine(chart: Chart, clock, *, demo: bool = True):
    """Wire a GameEngine with scoring (and a demo source if demo) over *clock*."""
    scoring = ScoringEngine()
    demo_source = DemoPlayer(chart) if demo else None
    engine = GameEngine(clock, scoring)
    engine.load(chart, demo_source=demo_source)
    return engine, scoring


def build_keymap(lane_count: int) -> dict[int, int]:
    """Map pygame key codes to lane indices (best-effort for up to 8 lanes)."""
    return {key: lane for lane, key in enumerate(PC_KEYS) if lane < lane_count}


# Produced-audio extensions tried when pairing with a MIDI, in preference order.
AUDIO_EXTS = ('.ogg', '.mp3', '.wav', '.flac')
MIDI_EXTS = ('.mid', '.midi')


def resolve_audio_source(midi_path: str, audio_path: str | None = None, *,
                         exists: Callable[[str], bool] = os.path.exists) -> str:
    """Choose what to play. Prefer an explicit *audio_path*; else a produced
    audio file paired with the MIDI by name (song.mid -> song.ogg/.mp3/...);
    else the MIDI itself (synthesized)."""
    if audio_path:
        return audio_path
    stem, _ = os.path.splitext(midi_path)
    for ext in AUDIO_EXTS:
        candidate = stem + ext
        if exists(candidate):
            return candidate
    return midi_path


def make_audio(midi_path: str, audio_path: str | None = None, *,
               backend=None, chart: Chart | None = None,
               synthesizer=synthesize_midi_to_wav) -> AudioPlayer:
    """Prepare the audio player from the resolved source (see
    resolve_audio_source). If no produced audio exists, synthesize the MIDI to a
    temporary WAV first; any load/synthesis failure degrades to a silent run."""
    audio = AudioPlayer(backend=backend)
    source = resolve_audio_source(midi_path, audio_path)
    if _is_midi_source(source):
        try:
            source = synthesizer(source, chart=chart)
            print(f"[MidiMania] synthesized MIDI preview audio: {source}")
        except Exception as exc:
            print(f"[MidiMania] MIDI synthesis unavailable, running silent: {exc}")
            return audio
    try:
        audio.load(source)
    except Exception as exc:  # unreadable file / unavailable audio device -> silent
        print(f"[MidiMania] audio unavailable, running silent: {exc}")
    return audio


def _is_midi_source(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in MIDI_EXTS


def run(midi_path: str, audio_path: str | None = None, *,
        demo: bool = True, mode: str = 'midi') -> None:
    """Launch the windowed game loop. Blocks until the window is closed."""
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    pygame.display.set_caption('MidiMania')

    chart = build_chart(midi_path, mode)
    audio = make_audio(midi_path, audio_path, chart=chart)

    engine, scoring = make_engine(chart, audio, demo=demo)
    renderer = Renderer(SIZE)
    keymap = build_keymap(chart.lane_count)
    engine.start()

    frame_clock = pygame.time.Clock()
    running = True
    while running:
        dt_ms = frame_clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    engine.resume() if engine.state.name == 'PAUSED' else engine.pause()
                elif not engine.is_demo() and event.key in keymap:
                    engine.handle_input(keymap[event.key])

        engine.update(dt_ms)
        renderer.render(screen, chart, engine.current_ms(), scoring,
                        state=engine.state, countdown=engine.countdown_value(),
                        is_demo=engine.is_demo())
        pygame.display.flip()

    pygame.quit()
