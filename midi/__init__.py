import time

from mido import MidiFile

mid = MidiFile('../resources/平和な日々.mid')
print(mid)

for track in mid.tracks:
    print(track)

for msg in mid.tracks[1]:
    time.sleep(msg.time/1000)
    if not msg.is_meta:
        print(msg.__dict__)