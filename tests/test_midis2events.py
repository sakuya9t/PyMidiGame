"""
Unit tests for midis2events.py after migration from pygame.midi to rtmidi.

Coverage:
  - rtmidi_msg_to_event: parses raw rtmidi byte lists into event dicts
  - simplify_midi_event: reduces event dict to {id, event} with mocked key name lookup
  - import guard: verifies midis2events has no pygame attribute
  - real MIDI file parsing (tests/fixtures/twinkle.mid from mfiles.co.uk)
"""
import sys
import os
import unittest
from unittest.mock import patch

import mido

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'twinkle.mid')

# Project root must be on sys.path so that all project imports resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from midis2events import (
    rtmidi_msg_to_event,
    simplify_midi_event,
    NOTE_ON,
    NOTE_OFF,
    KEY_AFTER_TOUCH,
    CONTROLLER_CHANGE,
    PROGRAM_CHANGE,
    CHANNEL_AFTER_TOUCH,
    PITCH_BEND,
)
from constants import EVENT_KEY_DOWN, EVENT_KEY_UP


class TestRtmidiMsgToEvent(unittest.TestCase):
    """Tests for rtmidi_msg_to_event — a pure byte-parser with no external deps."""

    # --- NOTE ON ---

    def test_note_on_command(self):
        event = rtmidi_msg_to_event([0x90, 60, 100])
        self.assertEqual(event['command'], NOTE_ON)

    def test_note_on_fields(self):
        event = rtmidi_msg_to_event([0x90, 60, 100])
        self.assertEqual(event['status'], 0x90)
        self.assertEqual(event['channel'], 0)
        self.assertEqual(event['data1'], 60)
        self.assertEqual(event['data2'], 100)

    def test_note_on_channel_extraction(self):
        # 0x95 = NOTE_ON on channel 5
        event = rtmidi_msg_to_event([0x95, 72, 80])
        self.assertEqual(event['command'], NOTE_ON)
        self.assertEqual(event['channel'], 5)

    # --- NOTE OFF ---

    def test_note_off_command(self):
        event = rtmidi_msg_to_event([0x80, 48, 0])
        self.assertEqual(event['command'], NOTE_OFF)

    def test_note_off_fields(self):
        event = rtmidi_msg_to_event([0x80, 48, 0])
        self.assertEqual(event['channel'], 0)
        self.assertEqual(event['data1'], 48)
        self.assertEqual(event['data2'], 0)

    # --- Other MIDI message types ---

    def test_controller_change(self):
        # 0xB0 = CONTROLLER_CHANGE on channel 0; data1=7 (volume), data2=100
        event = rtmidi_msg_to_event([0xB0, 7, 100])
        self.assertEqual(event['command'], CONTROLLER_CHANGE)
        self.assertEqual(event['data1'], 7)
        self.assertEqual(event['data2'], 100)

    def test_program_change(self):
        # 0xC0 = PROGRAM_CHANGE (2-byte message)
        event = rtmidi_msg_to_event([0xC0, 10])
        self.assertEqual(event['command'], PROGRAM_CHANGE)
        self.assertEqual(event['data1'], 10)
        self.assertEqual(event['data2'], 0)   # missing byte defaults to 0

    def test_pitch_bend(self):
        event = rtmidi_msg_to_event([0xE0, 0, 64])
        self.assertEqual(event['command'], PITCH_BEND)

    def test_key_after_touch(self):
        event = rtmidi_msg_to_event([0xA0, 60, 50])
        self.assertEqual(event['command'], KEY_AFTER_TOUCH)

    def test_channel_after_touch(self):
        event = rtmidi_msg_to_event([0xD0, 64])
        self.assertEqual(event['command'], CHANNEL_AFTER_TOUCH)

    # --- Missing-byte defaults ---

    def test_single_byte_message_defaults(self):
        # e.g. MIDI clock (0xF8) — unknown type, single byte
        event = rtmidi_msg_to_event([0xF8])
        self.assertEqual(event['data1'], 0)
        self.assertEqual(event['data2'], 0)

    def test_two_byte_message_data2_defaults(self):
        event = rtmidi_msg_to_event([0xC3, 5])
        self.assertEqual(event['data1'], 5)
        self.assertEqual(event['data2'], 0)

    # --- Channel 15 boundary ---

    def test_channel_15(self):
        event = rtmidi_msg_to_event([0x9F, 60, 64])   # NOTE_ON, channel 15
        self.assertEqual(event['command'], NOTE_ON)
        self.assertEqual(event['channel'], 15)


class TestSimplifyMidiEvent(unittest.TestCase):
    """Tests for simplify_midi_event.

    get_midi_key_name is mocked so tests are independent of config.json.
    """

    def _make_event(self, data1, data2, command=NOTE_ON, channel=0):
        status = 0x90 | channel
        return {
            'status': status,
            'command': command,
            'channel': channel,
            'data1': data1,
            'data2': data2,
        }

    def test_positive_velocity_is_key_down(self):
        raw = self._make_event(data1=60, data2=100)
        with patch('midis2events.get_midi_key_name', return_value='C4'):
            result = simplify_midi_event(raw)
        self.assertEqual(result['event'], EVENT_KEY_DOWN)
        self.assertEqual(result['id'], 'C4')

    def test_zero_velocity_is_key_up(self):
        # MIDI convention: NOTE_ON with velocity 0 == note-off
        raw = self._make_event(data1=60, data2=0)
        with patch('midis2events.get_midi_key_name', return_value='C4'):
            result = simplify_midi_event(raw)
        self.assertEqual(result['event'], EVENT_KEY_UP)

    def test_note_off_zero_velocity_is_key_up(self):
        raw = self._make_event(data1=60, data2=0, command=NOTE_OFF)
        with patch('midis2events.get_midi_key_name', return_value='C4'):
            result = simplify_midi_event(raw)
        self.assertEqual(result['event'], EVENT_KEY_UP)

    def test_data1_forwarded_to_key_name_lookup(self):
        raw = self._make_event(data1=69, data2=80)
        with patch('midis2events.get_midi_key_name', return_value='A4') as mock_fn:
            simplify_midi_event(raw)
        mock_fn.assert_called_once_with(69)

    def test_result_id_matches_key_name(self):
        raw = self._make_event(data1=69, data2=80)
        with patch('midis2events.get_midi_key_name', return_value='A4'):
            result = simplify_midi_event(raw)
        self.assertEqual(result['id'], 'A4')

    def test_velocity_boundary_one(self):
        # velocity=1 is the lowest "pressed" value
        raw = self._make_event(data1=60, data2=1)
        with patch('midis2events.get_midi_key_name', return_value='C4'):
            result = simplify_midi_event(raw)
        self.assertEqual(result['event'], EVENT_KEY_DOWN)

    def test_velocity_boundary_127(self):
        raw = self._make_event(data1=60, data2=127)
        with patch('midis2events.get_midi_key_name', return_value='C4'):
            result = simplify_midi_event(raw)
        self.assertEqual(result['event'], EVENT_KEY_DOWN)


class TestNoPygameMidiImport(unittest.TestCase):
    """Regression guard: midis2events must not import pygame (pygame.midi removed)."""

    def test_midis2events_has_no_pygame_attribute(self):
        import midis2events
        self.assertFalse(
            hasattr(midis2events, 'pygame'),
            "midis2events must not expose a 'pygame' name — pygame.midi was removed",
        )

    def test_pygame_midi_not_imported_by_midis2events(self):
        # Importing midis2events should not pull pygame.midi into sys.modules
        # (pygame itself may already be loaded by other imports, but .midi sub-module
        # should not appear due to midis2events alone — we check the attribute path).
        import midis2events
        midi_mod = sys.modules.get('pygame.midi')
        if midi_mod is not None:
            # If pygame.midi is in sys.modules it was loaded by something else —
            # confirm it is NOT accessible as an attribute of midis2events.
            self.assertIsNot(
                getattr(midis2events, 'pygame', None),
                midi_mod,
            )


class TestRealMidiFile(unittest.TestCase):
    """Integration tests using a real MIDI file (tests/fixtures/twinkle.mid).

    Source: https://www.mfiles.co.uk/downloads/twinkle-twinkle-little-star.mid

    Strategy: mido reads the file and exposes both parsed field values *and*
    raw bytes (msg.bytes()) identical to what an rtmidi callback delivers.
    We feed those bytes through rtmidi_msg_to_event and assert the decoded
    fields agree with mido's own parse — cross-validating our byte parser
    against an independent MIDI library.
    """

    @classmethod
    def setUpClass(cls):
        cls.midi = mido.MidiFile(FIXTURE_PATH)
        cls.channel_msgs = [
            msg
            for track in cls.midi.tracks
            for msg in track
            if not isinstance(msg, mido.MetaMessage)
        ]
        cls.note_ons  = [m for m in cls.channel_msgs if m.type == 'note_on']
        cls.note_offs = [m for m in cls.channel_msgs if m.type == 'note_off']
        cls.ccs       = [m for m in cls.channel_msgs if m.type == 'control_change']
        cls.pcs       = [m for m in cls.channel_msgs if m.type == 'program_change']

    # ------------------------------------------------------------------
    # Fixture sanity
    # ------------------------------------------------------------------

    def test_fixture_contains_expected_message_types(self):
        self.assertGreater(len(self.note_ons),  0, "no note_on in fixture")
        self.assertGreater(len(self.note_offs), 0, "no note_off in fixture")
        self.assertGreater(len(self.ccs),       0, "no control_change in fixture")
        self.assertGreater(len(self.pcs),       0, "no program_change in fixture")

    # ------------------------------------------------------------------
    # note_on cross-check
    # ------------------------------------------------------------------

    def test_note_on_command_field(self):
        for msg in self.note_ons:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['command'], NOTE_ON)

    def test_note_on_note_and_velocity(self):
        for msg in self.note_ons:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['data1'], msg.note)
                self.assertEqual(event['data2'], msg.velocity)

    def test_note_on_channel(self):
        for msg in self.note_ons:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['channel'], msg.channel)

    # ------------------------------------------------------------------
    # note_off cross-check
    # ------------------------------------------------------------------

    def test_note_off_command_field(self):
        for msg in self.note_offs:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['command'], NOTE_OFF)

    def test_note_off_note_and_velocity(self):
        for msg in self.note_offs:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['data1'], msg.note)
                self.assertEqual(event['data2'], msg.velocity)

    # ------------------------------------------------------------------
    # control_change cross-check
    # ------------------------------------------------------------------

    def test_control_change_command_field(self):
        for msg in self.ccs:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['command'], CONTROLLER_CHANGE)

    def test_control_change_control_and_value(self):
        for msg in self.ccs:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['data1'], msg.control)
                self.assertEqual(event['data2'], msg.value)

    # ------------------------------------------------------------------
    # program_change cross-check
    # ------------------------------------------------------------------

    def test_program_change_command_field(self):
        for msg in self.pcs:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['command'], PROGRAM_CHANGE)

    def test_program_change_program_number(self):
        for msg in self.pcs:
            with self.subTest(msg=msg):
                event = rtmidi_msg_to_event(msg.bytes())
                self.assertEqual(event['data1'], msg.program)
                self.assertEqual(event['data2'], 0)   # program_change has no third byte

    # ------------------------------------------------------------------
    # Full pipeline: bytes → rtmidi_msg_to_event → simplify_midi_event
    # ------------------------------------------------------------------

    def test_note_on_positive_velocity_yields_key_down(self):
        pressed = [m for m in self.note_ons if m.velocity > 0]
        self.assertGreater(len(pressed), 0)
        for msg in pressed:
            with self.subTest(msg=msg):
                result = simplify_midi_event(rtmidi_msg_to_event(msg.bytes()))
                self.assertEqual(result['event'], EVENT_KEY_DOWN)

    def test_note_on_zero_velocity_yields_key_up(self):
        # MIDI convention: note_on velocity=0 is an implicit note-off.
        released = [m for m in self.note_ons if m.velocity == 0]
        if not released:
            self.skipTest("fixture has no zero-velocity note_on messages")
        for msg in released:
            with self.subTest(msg=msg):
                result = simplify_midi_event(rtmidi_msg_to_event(msg.bytes()))
                self.assertEqual(result['event'], EVENT_KEY_UP)

    def test_note_off_yields_key_up(self):
        # All note_off in the fixture have velocity 0.
        for msg in self.note_offs:
            with self.subTest(msg=msg):
                result = simplify_midi_event(rtmidi_msg_to_event(msg.bytes()))
                self.assertEqual(result['event'], EVENT_KEY_UP)

    # ------------------------------------------------------------------
    # Spot-check: note number → key name (uses real config.json mapping)
    # ------------------------------------------------------------------

    def test_note_number_to_key_name(self):
        # Expected names derived from config.json midi-key table:
        #   note % 12 -> rank letter(s), note // 12 - 1 -> octave number
        expected = {
            48: 'C3',   # 48 % 12=0 -> C,  48//12-1=3
            52: 'E3',   # 52 % 12=4 -> E,  52//12-1=3
            55: 'G3',   # 55 % 12=7 -> G,  55//12-1=3
            60: 'C4',   # 60 % 12=0 -> C,  60//12-1=4
            62: 'D4',   # 62 % 12=2 -> D,  62//12-1=4
            67: 'G4',   # 67 % 12=7 -> G,  67//12-1=4
            69: 'A4',   # 69 % 12=9 -> A,  69//12-1=4
        }
        for note_num, expected_name in expected.items():
            candidates = [m for m in self.note_ons if m.note == note_num]
            if not candidates:
                continue
            result = simplify_midi_event(rtmidi_msg_to_event(candidates[0].bytes()))
            with self.subTest(note=note_num):
                self.assertEqual(result['id'], expected_name)


if __name__ == '__main__':
    unittest.main()
