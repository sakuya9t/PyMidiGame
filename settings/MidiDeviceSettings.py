from pygame import midi as pygame_midi
from rtmidi import midiutil


class MidiDeviceSettings:
    def __init__(self):
        self.midi_input = None

    def set_midi_device(self, device_id):
        midiutil.open_midiinput(device_id)
        self.midi_input = pygame_midi.Input(device_id)
