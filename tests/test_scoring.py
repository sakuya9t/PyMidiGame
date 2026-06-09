"""
Unit tests for src/game/scoring.py — Judgment and ScoringEngine.

Covers hit windows, score/combo/accuracy/rank, and the tick() timeout path,
per DESIGN.md §6. ScoringEngine satisfies the engine's Scoring Protocol
(reset/register_hit/tick).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.game.scoring import ScoringEngine, Judgment, GOOD_MS
from src.game.chart import Note, Chart
from src.midi.classifier import KeyboardClass

KB = KeyboardClass(name='25key', key_count=25, midi_low=48, midi_high=72, lane_count=25)


def _n(lane: int, time_ms: float, dur: float = 0.0) -> Note:
    return Note(lane=lane, midi_note=48 + lane, time_ms=time_ms, duration_ms=dur)


def _chart(notes: list[Note]) -> Chart:
    total = max((n.time_ms + n.duration_ms for n in notes), default=0.0)
    return Chart(notes=notes, kb_class=KB, mode='midi',
                 lane_count=25, total_duration_ms=total)


def _engine(notes: list[Note]) -> ScoringEngine:
    eng = ScoringEngine()
    eng.reset(_chart(notes))
    return eng


class TestReset(unittest.TestCase):

    def test_reset_clears_score_and_combo(self):
        eng = _engine([_n(0, 1000)])
        eng.register_hit(0, 1000)
        eng.reset(_chart([_n(0, 1000)]))
        self.assertEqual(eng.score, 0)
        self.assertEqual(eng.combo, 0)
        self.assertEqual(eng.max_combo, 0)

    def test_reset_clears_note_flags(self):
        notes = [_n(0, 1000)]
        eng = _engine(notes)
        eng.register_hit(0, 1000)
        self.assertTrue(notes[0].hit)
        eng.reset(_chart(notes))
        self.assertFalse(notes[0].hit)
        self.assertFalse(notes[0].missed)


class TestJudgmentCounts(unittest.TestCase):
    """Per-judgment tallies exposed for the results screen (DESIGN §15)."""

    def test_counts_start_at_zero(self):
        eng = _engine([_n(0, 1000)])
        self.assertEqual((eng.perfect, eng.great, eng.good, eng.miss), (0, 0, 0, 0))

    def test_counts_track_each_grade(self):
        eng = _engine([_n(0, 1000), _n(1, 2000), _n(2, 3000), _n(3, 4000)])
        eng.register_hit(0, 1000)        # PERFECT (0 ms)
        eng.register_hit(1, 2000 + 60)   # GREAT  (60 ms)
        eng.register_hit(2, 3000 + 100)  # GOOD   (100 ms)
        eng.tick(4000 + GOOD_MS + 1)     # note at 4000 times out -> MISS
        self.assertEqual((eng.perfect, eng.great, eng.good, eng.miss), (1, 1, 1, 1))

    def test_counts_cleared_on_reset(self):
        notes = [_n(0, 1000)]
        eng = _engine(notes)
        eng.register_hit(0, 1000)
        eng.reset(_chart(notes))
        self.assertEqual((eng.perfect, eng.great, eng.good, eng.miss), (0, 0, 0, 0))


class TestRecentHits(unittest.TestCase):
    """Successful hits leave short-lived events the renderer turns into sparks."""

    def test_successful_hit_records_a_fresh_event(self):
        eng = _engine([_n(2, 1000)])
        eng.register_hit(2, 1000)
        hits = eng.recent_hits(1000)
        self.assertEqual(len(hits), 1)
        lane, intensity = hits[0]
        self.assertEqual(lane, 2)
        self.assertAlmostEqual(intensity, 1.0)

    def test_stray_hit_records_no_event(self):
        eng = _engine([_n(2, 1000)])
        eng.register_hit(5, 1000)  # empty lane -> MISS, consumes no note
        self.assertEqual(eng.recent_hits(1000), [])

    def test_intensity_fades_with_age(self):
        eng = _engine([_n(0, 1000)])
        eng.register_hit(0, 1000)
        fresh = eng.recent_hits(1000)[0][1]
        aged = eng.recent_hits(1090)[0][1]
        self.assertGreater(fresh, aged)

    def test_event_expires_after_the_window(self):
        eng = _engine([_n(0, 1000)])
        eng.register_hit(0, 1000)
        self.assertEqual(eng.recent_hits(5000), [])

    def test_reset_clears_recent_hits(self):
        notes = [_n(0, 1000)]
        eng = _engine(notes)
        eng.register_hit(0, 1000)
        eng.reset(_chart(notes))
        self.assertEqual(eng.recent_hits(1000), [])

    def test_simultaneous_hits_in_different_lanes(self):
        eng = _engine([_n(0, 1000), _n(3, 1000)])
        eng.register_hit(0, 1000)
        eng.register_hit(3, 1000)
        lanes = sorted(lane for lane, _ in eng.recent_hits(1000))
        self.assertEqual(lanes, [0, 3])


class TestHitWindows(unittest.TestCase):

    def test_perfect_at_zero_offset(self):
        eng = _engine([_n(0, 1000)])
        self.assertEqual(eng.register_hit(0, 1000), Judgment.PERFECT)

    def test_perfect_boundary_35ms(self):
        eng = _engine([_n(0, 1000)])
        self.assertEqual(eng.register_hit(0, 1035), Judgment.PERFECT)

    def test_great_at_50ms(self):
        eng = _engine([_n(0, 1000)])
        self.assertEqual(eng.register_hit(0, 1050), Judgment.GREAT)

    def test_great_boundary_75ms(self):
        eng = _engine([_n(0, 1000)])
        self.assertEqual(eng.register_hit(0, 925), Judgment.GREAT)

    def test_good_at_100ms(self):
        eng = _engine([_n(0, 1000)])
        self.assertEqual(eng.register_hit(0, 1100), Judgment.GOOD)

    def test_good_boundary_120ms(self):
        eng = _engine([_n(0, 1000)])
        self.assertEqual(eng.register_hit(0, 1120), Judgment.GOOD)

    def test_outside_window_is_stray_miss(self):
        # 121 ms is outside GOOD; no note consumed, combo unchanged.
        notes = [_n(0, 1000)]
        eng = _engine(notes)
        self.assertEqual(eng.register_hit(0, 1121), Judgment.MISS)
        self.assertFalse(notes[0].hit)
        self.assertEqual(eng.combo, 0)
        self.assertEqual(eng.score, 0)

    def test_wrong_lane_does_not_match(self):
        notes = [_n(0, 1000)]
        eng = _engine(notes)
        self.assertEqual(eng.register_hit(1, 1000), Judgment.MISS)
        self.assertFalse(notes[0].hit)


class TestMatching(unittest.TestCase):

    def test_nearest_unresolved_note_chosen(self):
        notes = [_n(0, 1000), _n(0, 1080)]
        eng = _engine(notes)
        # Press at 1070 is nearer the 1080 note (dt 10) than 1000 (dt 70).
        eng.register_hit(0, 1070)
        self.assertFalse(notes[0].hit)
        self.assertTrue(notes[1].hit)

    def test_resolved_note_not_rehit(self):
        notes = [_n(0, 1000), _n(0, 1010)]
        eng = _engine(notes)
        eng.register_hit(0, 1000)  # resolves the 1000 note
        eng.register_hit(0, 1000)  # nearest unresolved is now the 1010 note
        self.assertTrue(notes[0].hit)
        self.assertTrue(notes[1].hit)


class TestScoreAndCombo(unittest.TestCase):

    def test_score_accumulates_by_multiplier(self):
        # 2 notes -> base 500000. PERFECT*1.0 + GREAT*0.7 = 500000 + 350000.
        eng = _engine([_n(0, 1000), _n(1, 2000)])
        eng.register_hit(0, 1000)   # PERFECT
        eng.register_hit(1, 2050)   # GREAT
        self.assertEqual(eng.score, 850000)

    def test_combo_increments_and_resets_on_tick_miss(self):
        notes = [_n(0, 1000), _n(1, 2000), _n(2, 3000)]
        eng = _engine(notes)
        eng.register_hit(0, 1000)
        eng.register_hit(1, 2000)
        self.assertEqual(eng.combo, 2)
        self.assertEqual(eng.max_combo, 2)
        eng.tick(3200)  # note at 3000 timed out (>3120) -> miss, combo reset
        self.assertEqual(eng.combo, 0)
        self.assertEqual(eng.max_combo, 2)
        self.assertTrue(notes[2].missed)


class TestTick(unittest.TestCase):

    def test_tick_before_window_close_no_miss(self):
        notes = [_n(0, 1000)]
        eng = _engine(notes)
        eng.tick(1120)  # exactly at GOOD edge, not past
        self.assertFalse(notes[0].missed)

    def test_tick_after_window_marks_miss(self):
        notes = [_n(0, 1000)]
        eng = _engine(notes)
        eng.tick(1121)
        self.assertTrue(notes[0].missed)

    def test_tick_does_not_remiss_resolved(self):
        notes = [_n(0, 1000)]
        eng = _engine(notes)
        eng.register_hit(0, 1000)
        eng.tick(5000)
        self.assertFalse(notes[0].missed)


class TestAccuracyAndRank(unittest.TestCase):

    def test_accuracy_perfect_plus_great_over_total(self):
        # 4 notes: 1 perfect + 1 great + 1 good + 1 miss -> (1+1)/4 = 0.5
        notes = [_n(0, 1000), _n(1, 2000), _n(2, 3000), _n(3, 4000)]
        eng = _engine(notes)
        eng.register_hit(0, 1000)   # PERFECT
        eng.register_hit(1, 2050)   # GREAT
        eng.register_hit(2, 3100)   # GOOD
        eng.tick(4200)              # 4th note miss
        self.assertAlmostEqual(eng.accuracy, 0.5)

    def test_rank_thresholds(self):
        self.assertEqual(ScoringEngine.rank_for(0.99), 'S')
        self.assertEqual(ScoringEngine.rank_for(0.95), 'A')
        self.assertEqual(ScoringEngine.rank_for(0.80), 'B')
        self.assertEqual(ScoringEngine.rank_for(0.65), 'C')
        self.assertEqual(ScoringEngine.rank_for(0.50), 'D')


class TestPerfectRun(unittest.TestCase):

    def test_all_perfect_yields_million_and_full_accuracy(self):
        notes = [_n(i % 8, i * 500.0) for i in range(20)]
        eng = _engine(notes)
        for n in notes:
            eng.register_hit(n.lane, n.time_ms)
        eng.tick(notes[-1].time_ms + 1000)
        self.assertEqual(eng.score, 1_000_000)
        self.assertAlmostEqual(eng.accuracy, 1.0)
        self.assertEqual(eng.rank(), 'S')
        self.assertEqual(eng.combo, 20)


class TestEmptyChart(unittest.TestCase):

    def test_empty_is_safe(self):
        eng = _engine([])
        eng.tick(1000)
        self.assertEqual(eng.score, 0)
        self.assertEqual(eng.register_hit(0, 0), Judgment.MISS)


if __name__ == '__main__':
    unittest.main()
