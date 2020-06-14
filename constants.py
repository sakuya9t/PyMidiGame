import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_PATH = os.path.join(ROOT_DIR, 'config/config.json')

EVENT_KEY_DOWN = 'EVENT_KEY_DOWN'
EVENT_KEY_UP = 'EVENT_KEY_UP'


class UI_CONSTANT:
    SCREEN_SIZE = (1024, 768)
    ID_OK_BTN = 'ok_btn'
    ID_CANCEL_BTN = 'cancel_btn'
    ID_MIDI_DEVICES_DROPDOWN = 'midi_devices_dropdown'
    ID_MIDI_MAP_KEY_BTN = 'make_map_btn'

    KEY_POPUP = 'key_mapping_popup'
    MESSAGE_WAIT_FOR_MIDI_INPUT = 'Please press key on your midi device'
    MESSAGE_WAIT_FOR_KEYBOARD_INPUT = 'Please press key on your keyboard'


class CONTROL_FLAGS:
    WAITING_FOR_MIDI_INPUT = 0
    WAITING_FOR_KEYBOARD_INPUT = 1


class STORE_KEYS:
    MIDI_INPUT_INDICATOR = 'midi_input_indicator'
    MIDI_KEY_MAP = 'key_maps'
    MIDI_DEVICES = 'midi_devices'
    CONFIGURING_KEY_MAP = 'configuring_key_map'
    SELECTED_MIDI_DEVICE = 'selected_midi_device'


class CONFIG_KEYS:
    MIDI_MAPPING = 'mapping'
    MIDI_KEY = 'midi-key'
    MIDI_DEVICE = 'midi-device'
    MIDI_DEVICE_ID = MIDI_DEVICE + '/device-id'


class COLORS:
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    DARK_BLUE = (0, 0, 128)
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    PINK = (237, 73, 179)
    GRAY_6 = (16, 16, 16)
    GRAY_12 = (32, 32, 32)
    GRAY_25 = (64, 64, 64)
    GRAY_50 = (128, 128, 128)


class SCENE_PARAMETER:
    TIMESTAMP = 'timestamp'
    START_TIMESTAMP = 'start_timestamp'
