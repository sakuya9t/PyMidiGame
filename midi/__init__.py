import time

from mido import MidiFile, MidiTrack

mid = MidiFile('../resources/平和な日々.mid')
print(mid)

print(type(mid.tracks[1]))

for msg in mid.tracks[1]:
    time.sleep(msg.time/1000)
    if not msg.is_meta:
        print(msg.__dict__)


def extract_midi_to_notes(midi_track: MidiTrack):
    notes = []
    timestamp = 0
