"""
Unit tests for src/game/engine.py — GameState and GameEngine.

The engine is an orchestrator over three injected collaborators (clock,
scoring, demo source). These tests drive it against fakes that record calls,
covering the full state machine per
ai-working-log/specs/2026-06-02-game-engine-design.md.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.game.engine import GameEngine, GameState
from src.game.chart import Chart
from src.midi.classifier import KeyboardClass
from src.input.signal import InputSignal


KB = KeyboardClass(name='25key', key_count=25, midi_low=48, midi_high=72, lane_count=25)


def _chart(total_duration_ms: float = 5000.0) -> Chart:
    """A minimal chart; the engine only reads total_duration_ms (and forwards
    the chart to scoring.reset)."""
    return Chart(notes=[], kb_class=KB, mode='midi',
                 lane_count=25, total_duration_ms=total_duration_ms)


# --- Fakes -----------------------------------------------------------------

class FakeClock:
    """Scriptable clock. The test sets current_ms directly; the clock records
    the order of lifecycle calls. Optionally resets position on stop()."""

    def __init__(self, reset_on_stop: bool = False):
        self.current = 0.0
        self.calls: list[str] = []
        self._playing = False
        self._reset_on_stop = reset_on_stop

    def play(self):
        self.calls.append('play')
        self._playing = True

    def pause(self):
        self.calls.append('pause')
        self._playing = False

    def resume(self):
        self.calls.append('resume')
        self._playing = True

    def stop(self):
        self.calls.append('stop')
        self._playing = False
        if self._reset_on_stop:
            self.current = 0.0

    def current_ms(self) -> float:
        return self.current

    def is_playing(self) -> bool:
        return self._playing


class FakeScoring:
    """Records reset/register_hit/tick calls."""

    def __init__(self):
        self.reset_charts: list = []
        self.hits: list[tuple[int, float]] = []
        self.ticks: list[float] = []

    def reset(self, chart):
        self.reset_charts.append(chart)

    def register_hit(self, lane: int, time_ms: float):
        self.hits.append((lane, time_ms))
        return None

    def tick(self, current_ms: float):
        self.ticks.append(current_ms)


class FakeDemoSource:
    """Pops signals whose time_ms <= now, like the real DemoPlayer."""

    def __init__(self, signals: list[InputSignal]):
        self._pending = sorted(signals, key=lambda s: s.time_ms)
        self.tick_times: list[float] = []

    def tick(self, current_ms: float) -> list[InputSignal]:
        self.tick_times.append(current_ms)
        due = [s for s in self._pending if s.time_ms <= current_ms]
        self._pending = [s for s in self._pending if s.time_ms > current_ms]
        return due


# --- Helpers ---------------------------------------------------------------

def _play(clock, scoring, chart=None, countdown_ms=3000):
    """Build an engine and advance it into PLAYING."""
    eng = GameEngine(clock, scoring, countdown_ms=countdown_ms)
    eng.load(chart or _chart())
    eng.start()
    eng.update(countdown_ms)  # cross the countdown threshold -> PLAYING
    return eng


# --- Tests -----------------------------------------------------------------

class TestLifecycle(unittest.TestCase):

    def test_initial_state_is_idle(self):
        eng = GameEngine(FakeClock(), FakeScoring())
        self.assertEqual(eng.state, GameState.IDLE)
        self.assertFalse(eng.is_finished())
        self.assertFalse(eng.is_demo())

    def test_start_before_load_raises(self):
        eng = GameEngine(FakeClock(), FakeScoring())
        with self.assertRaises(RuntimeError):
            eng.start()

    def test_update_before_load_raises(self):
        eng = GameEngine(FakeClock(), FakeScoring())
        with self.assertRaises(RuntimeError):
            eng.update(16)

    def test_load_keeps_idle_and_resets_scoring(self):
        scoring = FakeScoring()
        eng = GameEngine(FakeClock(), scoring)
        chart = _chart()
        eng.load(chart)
        self.assertEqual(eng.state, GameState.IDLE)
        self.assertEqual(scoring.reset_charts, [chart])

    def test_reload_resets_scoring_to_new_chart(self):
        scoring = FakeScoring()
        eng = GameEngine(FakeClock(), scoring)
        c1, c2 = _chart(), _chart(9000.0)
        eng.load(c1)
        eng.start()
        eng.load(c2)
        self.assertEqual(eng.state, GameState.IDLE)
        self.assertEqual(scoring.reset_charts, [c1, c2])

    def test_start_enters_countdown_without_starting_clock(self):
        clock = FakeClock()
        eng = GameEngine(clock, FakeScoring())
        eng.load(_chart())
        eng.start()
        self.assertEqual(eng.state, GameState.COUNTDOWN)
        self.assertNotIn('play', clock.calls)

    def test_start_when_not_idle_raises(self):
        eng = GameEngine(FakeClock(), FakeScoring())
        eng.load(_chart())
        eng.start()  # -> COUNTDOWN
        with self.assertRaises(RuntimeError):
            eng.start()


class TestCountdown(unittest.TestCase):

    def test_accumulates_below_threshold(self):
        clock = FakeClock()
        eng = GameEngine(clock, FakeScoring(), countdown_ms=3000)
        eng.load(_chart())
        eng.start()
        eng.update(1000)
        eng.update(1000)
        self.assertEqual(eng.state, GameState.COUNTDOWN)
        self.assertNotIn('play', clock.calls)

    def test_crossing_threshold_enters_playing_and_plays_once(self):
        clock = FakeClock()
        eng = GameEngine(clock, FakeScoring(), countdown_ms=3000)
        eng.load(_chart())
        eng.start()
        eng.update(1000)
        eng.update(1000)
        eng.update(1000)  # total 3000 -> threshold
        self.assertEqual(eng.state, GameState.PLAYING)
        self.assertEqual(clock.calls.count('play'), 1)

    def test_single_update_crossing_threshold(self):
        clock = FakeClock()
        eng = GameEngine(clock, FakeScoring(), countdown_ms=3000)
        eng.load(_chart())
        eng.start()
        eng.update(3000)
        self.assertEqual(eng.state, GameState.PLAYING)
        self.assertEqual(clock.calls.count('play'), 1)

    def test_demo_source_enters_demo_on_crossing(self):
        clock = FakeClock()
        eng = GameEngine(clock, FakeScoring(), countdown_ms=3000)
        eng.load(_chart(), demo_source=FakeDemoSource([]))
        eng.start()
        eng.update(3000)
        self.assertEqual(eng.state, GameState.DEMO)

    def test_countdown_value_counts_down(self):
        eng = GameEngine(FakeClock(), FakeScoring(), countdown_ms=3000)
        eng.load(_chart())
        eng.start()
        self.assertEqual(eng.countdown_value(), 3)
        eng.update(1000)
        self.assertEqual(eng.countdown_value(), 2)
        eng.update(1000)
        self.assertEqual(eng.countdown_value(), 1)
        eng.update(1000)
        self.assertEqual(eng.countdown_value(), 0)  # now PLAYING

    def test_current_ms_negative_preroll(self):
        eng = GameEngine(FakeClock(), FakeScoring(), countdown_ms=3000)
        eng.load(_chart())
        self.assertEqual(eng.current_ms(), -3000)  # IDLE
        eng.start()
        self.assertEqual(eng.current_ms(), -3000)  # COUNTDOWN, elapsed 0
        eng.update(1500)
        self.assertEqual(eng.current_ms(), -1500)  # rising toward 0


class TestPlaying(unittest.TestCase):

    def test_update_ticks_scoring_with_clock_time(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        clock.current = 1234.0
        eng.update(16)
        self.assertIn(1234.0, scoring.ticks)

    def test_handle_input_forwards_with_clock_stamp(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        clock.current = 2222.0
        eng.handle_input(5)  # engine stamps the time itself
        self.assertEqual(scoring.hits, [(5, 2222.0)])

    def test_handle_input_noop_in_countdown(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = GameEngine(clock, scoring)
        eng.load(_chart())
        eng.start()  # COUNTDOWN
        eng.handle_input(3)
        self.assertEqual(scoring.hits, [])

    def test_handle_input_noop_in_paused(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        eng.pause()
        eng.handle_input(3)
        self.assertEqual(scoring.hits, [])

    def test_handle_input_noop_in_demo(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = GameEngine(clock, scoring)
        eng.load(_chart(), demo_source=FakeDemoSource([]))
        eng.start()
        eng.update(3000)  # -> DEMO
        eng.handle_input(3)
        self.assertEqual(scoring.hits, [])


class TestDemo(unittest.TestCase):

    def _demo_engine(self, signals):
        clock, scoring = FakeClock(), FakeScoring()
        demo = FakeDemoSource(signals)
        eng = GameEngine(clock, scoring)
        eng.load(_chart(), demo_source=demo)
        eng.start()
        eng.update(3000)  # -> DEMO
        return eng, clock, scoring, demo

    def test_forwards_demo_signals_to_scoring(self):
        sig = InputSignal(lane=2, time_ms=500.0)
        eng, clock, scoring, demo = self._demo_engine([sig])
        clock.current = 500.0
        eng.update(16)
        self.assertIn((2, 500.0), scoring.hits)

    def test_demo_uses_signal_time_not_clock(self):
        # signal time 500 but clock at 999: the forwarded hit uses the signal's
        # own time (perfect demo timing), not the wall clock.
        sig = InputSignal(lane=1, time_ms=500.0)
        eng, clock, scoring, demo = self._demo_engine([sig])
        clock.current = 999.0
        eng.update(16)
        self.assertEqual(scoring.hits, [(1, 500.0)])

    def test_demo_still_ticks_scoring(self):
        eng, clock, scoring, demo = self._demo_engine([])
        clock.current = 700.0
        eng.update(16)
        self.assertIn(700.0, scoring.ticks)

    def test_is_demo_true_in_demo_and_across_pause(self):
        eng, clock, scoring, demo = self._demo_engine([])
        self.assertTrue(eng.is_demo())
        eng.pause()
        self.assertEqual(eng.state, GameState.PAUSED)
        self.assertTrue(eng.is_demo())


class TestFinish(unittest.TestCase):

    def test_stays_playing_before_tail(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring, chart=_chart(5000.0))  # tail at 7000
        clock.current = 6999.0
        eng.update(16)
        self.assertEqual(eng.state, GameState.PLAYING)

    def test_finishes_at_tail_and_stops_clock(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring, chart=_chart(5000.0))
        clock.current = 7000.0
        eng.update(16)
        self.assertEqual(eng.state, GameState.FINISHED)
        self.assertIn('stop', clock.calls)
        self.assertTrue(eng.is_finished())

    def test_update_noop_in_finished(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring, chart=_chart(5000.0))
        clock.current = 7000.0
        eng.update(16)  # -> FINISHED
        ticks_before = len(scoring.ticks)
        eng.update(16)
        self.assertEqual(len(scoring.ticks), ticks_before)

    def test_finish_time_cached_against_resetting_stop(self):
        clock = FakeClock(reset_on_stop=True)
        scoring = FakeScoring()
        eng = _play(clock, scoring, chart=_chart(5000.0))
        clock.current = 7000.0
        eng.update(16)  # finish; stop() resets clock.current to 0
        self.assertEqual(clock.current, 0.0)
        self.assertEqual(eng.current_ms(), 7000.0)  # cached, not the reset clock


class TestPauseResume(unittest.TestCase):

    def test_pause_from_playing(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        eng.pause()
        self.assertEqual(eng.state, GameState.PAUSED)
        self.assertIn('pause', clock.calls)

    def test_paused_current_ms_frozen(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        clock.current = 3300.0
        eng.pause()
        self.assertEqual(eng.current_ms(), 3300.0)

    def test_resume_returns_to_playing(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        eng.pause()
        eng.resume()
        self.assertEqual(eng.state, GameState.PLAYING)
        self.assertIn('resume', clock.calls)

    def test_pause_resume_from_demo_returns_to_demo(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = GameEngine(clock, scoring)
        eng.load(_chart(), demo_source=FakeDemoSource([]))
        eng.start()
        eng.update(3000)  # -> DEMO
        eng.pause()
        eng.resume()
        self.assertEqual(eng.state, GameState.DEMO)

    def test_redundant_pause_is_noop(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        eng.pause()
        eng.pause()  # redundant
        self.assertEqual(clock.calls.count('pause'), 1)

    def test_redundant_resume_is_noop(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        eng.resume()  # not paused -> no-op
        self.assertNotIn('resume', clock.calls)


class TestStop(unittest.TestCase):
    """stop() aborts a run early (e.g. quitting to the menu mid-song)."""

    def test_stop_halts_clock_and_returns_to_idle(self):
        clock, scoring = FakeClock(), FakeScoring()
        eng = _play(clock, scoring)
        self.assertTrue(clock.is_playing())   # sanity: audio is running
        eng.stop()
        self.assertFalse(clock.is_playing())
        self.assertIn('stop', clock.calls)
        self.assertIs(eng.state, GameState.IDLE)

    def test_stop_during_countdown_is_safe(self):
        # Aborting before play starts (clock not yet playing) must not raise.
        clock, scoring = FakeClock(), FakeScoring()
        eng = GameEngine(clock, scoring, countdown_ms=3000)
        eng.load(_chart())
        eng.start()  # COUNTDOWN
        eng.stop()
        self.assertIs(eng.state, GameState.IDLE)
        self.assertIn('stop', clock.calls)


if __name__ == '__main__':
    unittest.main()
