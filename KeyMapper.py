import pyautogui
from pyautogui import keyDown, keyUp

from config.Config import Config
from constants import EVENT_KEY_DOWN, EVENT_KEY_UP, CONFIG_KEYS

pyautogui.PAUSE = 0
config = Config('config/config.json')
key_name_map = config.get(CONFIG_KEYS.MIDI_KEY)
key_code_map = {value: key for key, value in key_name_map.items()}


class KeyMapper:
    def __init__(self):
        self.key_map = config.get(CONFIG_KEYS.MIDI_MAPPING)

    def map_midi(self, midi_events):
        for midi_event in midi_events:
            key_id = midi_event['id']
            if key_id not in self.key_map.keys():
                continue
            if midi_event['event'] == EVENT_KEY_DOWN:
                keyDown(self.key_map[key_id])
            elif midi_event['event'] == EVENT_KEY_UP:
                keyUp(self.key_map[key_id])


def get_midi_key_name(key_id):
    if key_id < 0:
        return 'invalid key (<0)'
    key_rank = key_name_map[str(key_id % 12)]
    scale = key_id // 12 - 1
    return '{}{}'.format(key_rank, scale)


def get_midi_key_code(key_name):
    if not isinstance(key_name, str):
        raise Exception('Key name need to be a string.')
    rank = key_name[0:2] if key_name[1] == '#' else key_name[0:1]
    scale = int(key_name[len(rank):])
    return int(key_code_map[rank]) + 12 * (scale + 1)


def is_black_key(key_name):
    return '#' in key_name
