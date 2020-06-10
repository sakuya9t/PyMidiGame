from mido import MidiFile, tempo2bpm, tick2second

from KeyMapper import get_midi_key_name


class TimeSignature:
    def __init__(self, numerator, denominator):
        self.numerator = numerator
        self.denominator = denominator


class MidiInfo:
    def __init__(self, file_name):
        self.mid_file = MidiFile(file_name)
        self.ppq = self.mid_file.ticks_per_beat
        self.tempo = None
        self.bpm = None
        self.time_signature = None
        self.__get_bpm__()

    def __str__(self):
        return str([str(x) for x in self.to_note_list()])

    def __get_bpm__(self):
        messages = [msg.__dict__ for msg in self.mid_file.tracks[0]]
        tempo_messages = [msg for msg in messages if msg['type'] == 'set_tempo']
        time_signature_messages = [msg for msg in messages if msg['type'] == 'time_signature']
        if len(tempo_messages) == 0:
            raise Exception('No tempo info in midi file.')
        # can have multiple tempo messages if the midi changes tempo in the middle
        self.time_signature = TimeSignature(time_signature_messages[0]['numerator'], time_signature_messages[0]['denominator'])
        self.tempo = tempo_messages[0]['tempo']
        self.bpm = round(tempo2bpm(self.tempo), 2)

    def __tick_to_beats__(self, n_ticks):
        n_seconds = tick2second(n_ticks, self.ppq, self.tempo)
        return round(n_seconds / (60 / self.bpm), 2)

    def to_note_list(self):
        midi_track = self.mid_file.tracks[1]
        notes = []
        ongoing_notes = {}
        timestamp = 0
        for msg in midi_track:
            msg_data = msg.__dict__
            msg_type = msg_data['type']
            if msg.is_meta or msg_type not in ['note_on', 'note_off']:
                continue
            msg_note, msg_time = msg_data['note'], self.__tick_to_beats__(msg_data['time'])
            timestamp += msg_time
            if msg_type == 'note_on':
                ongoing_notes[msg_note] = timestamp
            elif msg_type == 'note_off':
                duration = timestamp - ongoing_notes[msg_note]
                notes.append(
                    Note(start=ongoing_notes[msg_note], duration=duration, note_name=get_midi_key_name(msg_note)))
                del ongoing_notes[msg_note]
        return notes


class Note:
    def __init__(self, start, duration, note_name):
        self.start = start
        self.duration = duration
        self.note_name = note_name

    def __str__(self):
        return str({'start': self.start, 'duration': self.duration, 'note_name': self.note_name})


if __name__ == '__main__':
    midi_info = MidiInfo('../resources/chords.mid')
    print(midi_info.time_signature)
    print(midi_info.bpm)
    print(midi_info)

    midi_info_2 = MidiInfo('../resources/平和な日々.mid')
    print(midi_info_2.time_signature)
    print(midi_info_2.bpm)
    print(midi_info_2)
