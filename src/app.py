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
from enum import Enum, auto
from typing import Callable

import pygame
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor,
)

from src.midi.parser import MidiParser
from src.midi.classifier import classify
from src.game.chart import Chart, ChartBuilder
from src.game.engine import GameEngine
from src.game.scoring import ScoringEngine
from src.game.demo import DemoPlayer
from src.audio.player import AudioPlayer
from src.audio.synth import synthesize_midi_to_wav
from src.ui.renderer import Renderer
from src.ui.hud import HudOverlay
from src.ui.results import ResultsScreen
from src.ui.gl_overlay import SurfacePresenter
from src.ui.menu import scan_songs, SongMenu, SongEntry, StartGame, QuitGame

SIZE = (960, 720)


def _open_gl_window(size: tuple[int, int]) -> pygame.Surface:
    """Open the double-buffered OpenGL window used for the whole app."""
    screen = pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.OPENGL)
    pygame.display.set_caption('MidiMania')
    return screen


def _gl_clear() -> None:
    glClearColor(0.015, 0.03, 0.07, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

# PC keyboard lane mapping for 9 lanes: A S D F Space J K L ;
PC_KEYS = [pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_f,
           pygame.K_SPACE,
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
    """Map pygame key codes to lane indices (best-effort for up to 9 PC lanes)."""
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
    """Launch the windowed game loop for a single chart. Blocks until closed."""
    pygame.init()
    _open_gl_window(SIZE)

    chart = build_chart(midi_path, mode)
    audio = make_audio(midi_path, audio_path, chart=chart)

    engine, scoring = make_engine(chart, audio, demo=demo)
    renderer = Renderer(SIZE)
    hud = HudOverlay(SIZE)
    presenter = SurfacePresenter(SIZE)
    overlay = pygame.Surface(SIZE, pygame.SRCALPHA)
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
                elif not engine.is_demo() and event.key in keymap:
                    engine.handle_input(keymap[event.key])
                elif event.key == pygame.K_p:
                    engine.resume() if engine.state.name == 'PAUSED' else engine.pause()

        engine.update(dt_ms)
        renderer.render(chart, engine.current_ms())
        hud.render(overlay, scoring, state=engine.state,
                   countdown=engine.countdown_value(), is_demo=engine.is_demo())
        presenter.present(overlay)
        pygame.display.flip()

    pygame.quit()


# --- App: menu -> play -> results -> menu loop -----------------------------

class AppScreen(Enum):
    MENU = auto()
    PLAYING = auto()
    RESULTS = auto()


class App:
    """Top-level state machine owning the window and the screen loop.

    Screens (AppScreen): MENU (SongMenu), PLAYING (GameEngine + Renderer), and
    RESULTS (the renderer's FINISHED overlay). The per-frame logic lives in
    handle_event/update/render/step so it can be driven headlessly in tests; run()
    wraps step() with the real pygame event pump and display flip.

    audio_factory(entry, chart) -> Clock is injectable so tests can supply a
    manual clock; it defaults to the make_audio pipeline (produced audio, else a
    synthesized MIDI preview, else silent).
    """

    def __init__(self, songs_dir: str = 'songs', size: tuple[int, int] = SIZE, *,
                 surface: pygame.Surface | None = None,
                 scan: Callable[[str], list[SongEntry]] = scan_songs,
                 audio_factory: Callable[[SongEntry, Chart], object] | None = None) -> None:
        self._songs_dir = songs_dir
        self._size = size
        self._songs = scan(songs_dir)
        self._menu = SongMenu(self._songs, size)
        self._renderer = Renderer(size)
        self._hud = HudOverlay(size)
        self._results = ResultsScreen(size)
        self._presenter = SurfacePresenter(size)
        self._surface = surface
        self._gl = False  # set True once run() opens a real OpenGL window
        self._audio_factory = audio_factory or self._default_audio
        self._screen = AppScreen.MENU
        self._engine: GameEngine | None = None
        self._scoring: ScoringEngine | None = None
        self._chart: Chart | None = None
        self._keymap: dict[int, int] = {}
        self._selection: tuple[SongEntry, str] | None = None
        self._running = True

    # --- queries -----------------------------------------------------------

    @property
    def screen(self) -> AppScreen:
        return self._screen

    @property
    def songs(self) -> list[SongEntry]:
        return self._songs

    @property
    def engine(self) -> GameEngine | None:
        return self._engine

    @property
    def scoring(self) -> ScoringEngine | None:
        return self._scoring

    @property
    def chart(self) -> Chart | None:
        return self._chart

    def _default_audio(self, entry: SongEntry, chart: Chart):
        return make_audio(entry.midi_path, entry.audio_path, chart=chart)

    # --- transitions -------------------------------------------------------

    def start_game(self, entry: SongEntry, input_mode: str) -> None:
        """Load *entry* and enter PLAYING. PC Keyboard plays compressed lanes
        ('pc'); Demo auto-plays the full-fidelity layout ('midi')."""
        demo = input_mode == 'demo'
        chart_mode = 'midi' if demo else 'pc'
        self._chart = build_chart(entry.midi_path, chart_mode)
        clock = self._audio_factory(entry, self._chart)
        self._engine, self._scoring = make_engine(self._chart, clock, demo=demo)
        self._keymap = build_keymap(self._chart.lane_count)
        self._selection = (entry, input_mode)
        self._engine.start()
        self._screen = AppScreen.PLAYING

    def to_menu(self) -> None:
        self._screen = AppScreen.MENU

    def retry(self) -> None:
        entry, input_mode = self._selection
        self.start_game(entry, input_mode)

    # --- per-frame ---------------------------------------------------------

    def handle_event(self, event) -> None:
        if self._screen is AppScreen.MENU:
            self._handle_menu(event)
        elif self._screen is AppScreen.PLAYING:
            self._handle_playing(event)
        elif self._screen is AppScreen.RESULTS:
            self._handle_results(event)

    def _handle_menu(self, event) -> None:
        action = self._menu.handle_event(event)
        if isinstance(action, StartGame):
            self.start_game(action.entry, action.input_mode)
        elif isinstance(action, QuitGame):
            self._running = False

    def _handle_playing(self, event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.to_menu()
        elif event.key == pygame.K_p:
            if self._engine.state.name == 'PAUSED':
                self._engine.resume()
            else:
                self._engine.pause()
        elif not self._engine.is_demo() and event.key in self._keymap:
            self._engine.handle_input(self._keymap[event.key])

    def _handle_results(self, event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_r:
            self.retry()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.to_menu()

    def update(self, dt_ms: float) -> None:
        if self._screen is AppScreen.PLAYING:
            self._engine.update(dt_ms)
            if self._engine.is_finished():
                self._screen = AppScreen.RESULTS

    def render(self) -> None:
        """Draw the current screen. The 2D layers (menu, HUD) are drawn onto the
        offscreen surface; when a GL window is open they are composited as a
        textured quad over the 3D playfield. Without GL (headless tests) only the
        2D layers are drawn, exercising them without a context."""
        if self._screen is AppScreen.MENU:
            if self._surface is not None:
                self._menu.render(self._surface)
            if self._gl:
                _gl_clear()
                self._presenter.present(self._surface)
        elif self._screen is AppScreen.RESULTS:
            if self._surface is not None and self._selection is not None:
                entry, input_mode = self._selection
                self._results.render(self._surface, self._scoring, entry, input_mode)
            if self._gl:
                _gl_clear()
                self._presenter.present(self._surface)
        else:  # PLAYING
            if self._surface is not None:
                self._hud.render(
                    self._surface, self._scoring, state=self._engine.state,
                    countdown=self._engine.countdown_value(),
                    is_demo=self._engine.is_demo())
            if self._gl:
                self._renderer.render(self._chart, self._engine.current_ms())
                self._presenter.present(self._surface)

    def step(self, dt_ms: float, events) -> bool:
        """Advance one frame over *events*; returns whether the app keeps running."""
        for event in events:
            if event.type == pygame.QUIT:
                self._running = False
            else:
                self.handle_event(event)
        self.update(dt_ms)
        self.render()
        return self._running

    def run(self) -> None:
        """Open the GL window and run the menu->play->results loop until quit."""
        pygame.init()
        _open_gl_window(self._size)
        self._gl = True
        self._surface = pygame.Surface(self._size, pygame.SRCALPHA)
        frame_clock = pygame.time.Clock()
        while self._running:
            dt_ms = frame_clock.tick(60)
            self.step(dt_ms, pygame.event.get())
            pygame.display.flip()
        pygame.quit()
