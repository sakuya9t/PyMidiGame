import rtmidi
from rtmidi.midiutil import get_api_from_environment


class MidiControl:
    @staticmethod
    def get_input_midi_devices(api=rtmidi.API_UNSPECIFIED):
        midiin = rtmidi.MidiIn(get_api_from_environment(api))
        ports = midiin.get_ports()
        return ["[{}] {}".format(portno, name) for portno, name in enumerate(ports)]