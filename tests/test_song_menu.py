"""
Tests for src/ui/menu.py — the song library scanner and the SongMenu screen.

scan_songs reads a songs/ directory of per-song folders into displayable
SongEntry metadata; bad or chartless folders are skipped, not fatal. SongMenu's
navigation logic is unit-tested directly; its pygame drawing is exercised by a
headless smoke test under SDL's dummy video driver.
"""
import sys
import os
import json
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from src.ui.menu import (
    SongEntry, scan_songs, SongMenu, StartGame, QuitGame, SELECTABLE_MODES,
)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
TWINKLE = os.path.join(FIXTURES, 'twinkle.mid')
BACH = os.path.join(FIXTURES, 'bach-cello-type0.mid')

SIZE = (1366, 768)  # shipping 16:9 resolution


def _make_song(root, name, *, midi=TWINKLE, chart_name='chart.mid',
               meta=None, audio_ext=None):
    """Create songs/<name>/ with a chart (copied from *midi*) and optional
    meta.json / produced audio sibling. Returns the song dir path."""
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    if midi is not None:
        shutil.copy(midi, os.path.join(d, chart_name))
    if meta is not None:
        with open(os.path.join(d, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f)
    if audio_ext is not None:
        # An empty placeholder is enough for path resolution.
        open(os.path.join(d, 'chart' + audio_ext), 'w').close()
    return d


class TestSongEntryDataclass(unittest.TestCase):

    def test_fields(self):
        e = SongEntry(name='x', dir='/x', midi_path='/x/c.mid', audio_path=None,
                      title='X', artist='', key_class='32key',
                      total_duration_ms=1000.0, bpm=None)
        self.assertEqual(e.name, 'x')
        self.assertEqual(e.key_class, '32key')
        self.assertIsNone(e.audio_path)


class TestScanSongs(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='midimania-songs-')
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_missing_dir_is_empty(self):
        self.assertEqual(scan_songs(os.path.join(self.root, 'nope')), [])

    def test_empty_dir_is_empty(self):
        self.assertEqual(scan_songs(self.root), [])

    def test_scans_a_song_folder(self):
        _make_song(self.root, 'twinkle')
        songs = scan_songs(self.root)
        self.assertEqual(len(songs), 1)
        s = songs[0]
        self.assertEqual(s.name, 'twinkle')
        self.assertEqual(s.midi_path, os.path.join(self.root, 'twinkle', 'chart.mid'))
        self.assertEqual(s.key_class, '32key')          # twinkle range -> 32key
        self.assertGreater(s.total_duration_ms, 0.0)

    def test_meta_json_overrides_title_artist_bpm(self):
        _make_song(self.root, 'twinkle',
                   meta={'title': 'Greensleeves', 'artist': 'Trad.', 'bpm': 90})
        s = scan_songs(self.root)[0]
        self.assertEqual(s.title, 'Greensleeves')
        self.assertEqual(s.artist, 'Trad.')
        self.assertEqual(s.bpm, 90)

    def test_defaults_without_meta(self):
        _make_song(self.root, 'bach-cello', midi=BACH)
        s = scan_songs(self.root)[0]
        self.assertEqual(s.title, 'Bach Cello')        # prettified dir name
        self.assertEqual(s.artist, '')
        self.assertIsNone(s.bpm)

    def test_folder_without_chart_is_skipped(self):
        os.makedirs(os.path.join(self.root, 'empty'))
        self.assertEqual(scan_songs(self.root), [])

    def test_malformed_midi_is_skipped(self):
        d = os.path.join(self.root, 'broken')
        os.makedirs(d)
        with open(os.path.join(d, 'chart.mid'), 'wb') as f:
            f.write(b'not a midi file at all')
        self.assertEqual(scan_songs(self.root), [])

    def test_sorted_by_name(self):
        _make_song(self.root, 'zeta')
        _make_song(self.root, 'alpha')
        names = [s.name for s in scan_songs(self.root)]
        self.assertEqual(names, ['alpha', 'zeta'])

    def test_resolves_produced_audio_sibling(self):
        _make_song(self.root, 'twinkle', audio_ext='.ogg')
        s = scan_songs(self.root)[0]
        self.assertEqual(s.audio_path,
                         os.path.join(self.root, 'twinkle', 'chart.ogg'))

    def test_audio_none_when_no_produced_sibling(self):
        _make_song(self.root, 'twinkle')
        self.assertIsNone(scan_songs(self.root)[0].audio_path)

    def test_falls_back_to_any_mid_when_no_chart_mid(self):
        _make_song(self.root, 'twinkle', chart_name='song.mid')
        s = scan_songs(self.root)[0]
        self.assertEqual(s.midi_path,
                         os.path.join(self.root, 'twinkle', 'song.mid'))


class TestSongMenuNavigation(unittest.TestCase):

    def _entry(self, name):
        return SongEntry(name=name, dir='/' + name, midi_path='/%s/c.mid' % name,
                         audio_path=None, title=name.title(), artist='',
                         key_class='32key', total_duration_ms=1000.0, bpm=None)

    def _menu(self, n=3):
        return SongMenu([self._entry('s%d' % i) for i in range(n)], SIZE)

    def _key(self, key):
        return pygame.event.Event(pygame.KEYDOWN, key=key)

    def test_down_moves_selection(self):
        m = self._menu()
        self.assertIsNone(m.handle_event(self._key(pygame.K_DOWN)))
        self.assertEqual(m.selected_index, 1)

    def test_up_is_clamped_at_top(self):
        m = self._menu()
        m.handle_event(self._key(pygame.K_UP))
        self.assertEqual(m.selected_index, 0)

    def test_down_is_clamped_at_bottom(self):
        m = self._menu(n=2)
        m.handle_event(self._key(pygame.K_DOWN))
        m.handle_event(self._key(pygame.K_DOWN))
        m.handle_event(self._key(pygame.K_DOWN))
        self.assertEqual(m.selected_index, 1)

    def test_right_cycles_mode_and_wraps(self):
        m = self._menu()
        self.assertEqual(SELECTABLE_MODES[m.mode_index], 'pc')
        m.handle_event(self._key(pygame.K_RIGHT))
        self.assertEqual(SELECTABLE_MODES[m.mode_index], 'demo')
        m.handle_event(self._key(pygame.K_RIGHT))
        self.assertEqual(SELECTABLE_MODES[m.mode_index], 'pc')   # wrapped

    def test_enter_starts_selected_song_with_mode(self):
        m = self._menu()
        m.handle_event(self._key(pygame.K_DOWN))         # select s1
        m.handle_event(self._key(pygame.K_RIGHT))        # mode -> demo
        action = m.handle_event(self._key(pygame.K_RETURN))
        self.assertIsInstance(action, StartGame)
        self.assertEqual(action.entry.name, 's1')
        self.assertEqual(action.input_mode, 'demo')

    def test_escape_quits(self):
        m = self._menu()
        self.assertIsInstance(m.handle_event(self._key(pygame.K_ESCAPE)), QuitGame)

    def test_enter_on_empty_library_is_noop(self):
        m = SongMenu([], SIZE)
        self.assertIsNone(m.handle_event(self._key(pygame.K_RETURN)))

    def test_midi_is_not_selectable(self):
        self.assertNotIn('midi', SELECTABLE_MODES)


class TestSongMenuRender(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface(SIZE)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _entry(self, name):
        return SongEntry(name=name, dir='/' + name, midi_path='/%s/c.mid' % name,
                         audio_path=None, title=name.title(), artist='Artist',
                         key_class='49key', total_duration_ms=125000.0, bpm=120)

    def test_renders_populated_menu(self):
        m = SongMenu([self._entry('a'), self._entry('b')], SIZE)
        m.render(self.surface)  # must not raise

    def test_renders_empty_menu(self):
        SongMenu([], SIZE).render(self.surface)  # must not raise


if __name__ == '__main__':
    unittest.main()
