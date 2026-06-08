"""
Tests for src/midi/device.py — MIDI input device I/O.

rtmidi is wrapped behind an injectable backend, so these run headlessly with a
FakeMidiBackend that serves scripted ports and raw messages — no hardware.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.midi.device import (
    MidiInputDevice, list_input_ports, guess_key_count,
)


class FakeMidiBackend:
    """Stand-in for rtmidi.MidiIn: scripted ports + a queue of raw messages.

    Each queued item is (message_bytes, delta_time) as rtmidi returns from
    get_message(); get_message() pops one or returns None when empty."""

    def __init__(self, ports=(), messages=()):
        self._ports = list(ports)
        self._queue = list(messages)
        self.opened = None
        self.closed = False

    def get_ports(self):
        return list(self._ports)

    def open_port(self, index):
        self.opened = index

    def get_message(self):
        return self._queue.pop(0) if self._queue else None

    def close_port(self):
        self.closed = True


def _msg(*bytes_):
    return (list(bytes_), 0.0)


class TestListPorts(unittest.TestCase):

    def test_lists_backend_ports(self):
        backend = FakeMidiBackend(ports=['Oxygen Pro 49 1', 'Focusrite USB MIDI 0'])
        self.assertEqual(list_input_ports(backend),
                         ['Oxygen Pro 49 1', 'Focusrite USB MIDI 0'])


class TestOpenClose(unittest.TestCase):

    def test_open_forwards_index(self):
        backend = FakeMidiBackend(ports=['a', 'b'])
        dev = MidiInputDevice(backend)
        dev.open(1)
        self.assertEqual(backend.opened, 1)

    def test_close_forwards(self):
        backend = FakeMidiBackend(ports=['a'])
        dev = MidiInputDevice(backend)
        dev.open(0)
        dev.close()
        self.assertTrue(backend.closed)


class TestPollParsing(unittest.TestCase):

    def test_note_on_parsed(self):
        backend = FakeMidiBackend(messages=[_msg(0x90, 60, 100)])
        dev = MidiInputDevice(backend)
        msgs = dev.poll()
        self.assertEqual(len(msgs), 1)
        self.assertEqual((msgs[0].kind, msgs[0].note, msgs[0].velocity),
                         ('note_on', 60, 100))

    def test_note_off_parsed(self):
        backend = FakeMidiBackend(messages=[_msg(0x80, 62, 0)])
        dev = MidiInputDevice(backend)
        self.assertEqual(dev.poll()[0].kind, 'note_off')

    def test_note_on_velocity_zero_is_note_off(self):
        backend = FakeMidiBackend(messages=[_msg(0x90, 64, 0)])
        dev = MidiInputDevice(backend)
        msg = dev.poll()[0]
        self.assertEqual((msg.kind, msg.note), ('note_off', 64))

    def test_non_note_message_is_other(self):
        backend = FakeMidiBackend(messages=[_msg(0xB0, 7, 100)])  # control change
        dev = MidiInputDevice(backend)
        self.assertEqual(dev.poll()[0].kind, 'other')

    def test_poll_drains_all_then_empties(self):
        backend = FakeMidiBackend(messages=[_msg(0x90, 60, 90), _msg(0x90, 62, 90)])
        dev = MidiInputDevice(backend)
        first = dev.poll()
        self.assertEqual([m.note for m in first], [60, 62])
        self.assertEqual(dev.poll(), [])  # queue drained

    def test_channel_is_ignored(self):
        # note_on on channel 3 (0x92) still parses as note_on.
        backend = FakeMidiBackend(messages=[_msg(0x92, 67, 80)])
        dev = MidiInputDevice(backend)
        self.assertEqual(dev.poll()[0].kind, 'note_on')


class TestGuessKeyCount(unittest.TestCase):

    def test_recognizes_known_count_in_name(self):
        self.assertEqual(guess_key_count('Oxygen Pro 49 1'), 49)

    def test_recognizes_61(self):
        self.assertEqual(guess_key_count('Keystation 61 MK3'), 61)

    def test_none_when_no_known_count(self):
        self.assertIsNone(guess_key_count('Focusrite USB MIDI 0'))


if __name__ == '__main__':
    unittest.main()
