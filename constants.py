EVENT_KEY_DOWN = 'EVENT_KEY_DOWN'
EVENT_KEY_UP = 'EVENT_KEY_UP'


class UI_CONSTANT:
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


class CONFIG_KEYS:
    MIDI_MAPPING = 'mapping'
    MIDI_KEY = 'midi-key'
    MIDI_DEVICE = 'midi-device'
    MIDI_DEVICE_ID = MIDI_DEVICE + '/device-id'
