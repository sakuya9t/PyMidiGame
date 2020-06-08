import pygame
from pygame import midi as pygame_midi

from config.Config import Config
from InputQueue import InputMidiQueue, InputUIEventQueue, InputKeyboardEventQueue
from constants import UI_CONSTANT, CONTROL_FLAGS, STORE_KEYS, CONFIG_KEYS
from window import window_control, window_painter
from KeyCodeConstants import get_key_code

config = Config('config/config.json')
key_name = config.get(CONFIG_KEYS.MIDI_KEY)


class game_controller:
    def __init__(self):
        pygame.init()
        self.font = None
        self.ui_control = {}
        self.store = Store()
        self.init_store()
        self.display_controller = None
        self.painter = None
        self.control_flags = {}
        self.init_control_flags()
        self.config = config

    def start(self):
        pygame.font.init()
        self.font = pygame.font.SysFont(None, 24)
        pygame_midi.init()
        self.display_controller = window_control(self.ui_control)
        self.painter = window_painter(self.display_controller, self.font, self.store)
        self.display_controller.painter = self.painter

    def init_store(self):
        configed_key_map = config.get(CONFIG_KEYS.MIDI_MAPPING)
        key_map = [[key, pygame.key.name(get_key_code(value))] for key, value in configed_key_map.items()]
        self.store.put(STORE_KEYS.MIDI_INPUT_INDICATOR, UI_CONSTANT.MESSAGE_WAIT_FOR_MIDI_INPUT)
        self.store.put(STORE_KEYS.MIDI_KEY_MAP, [['MIDI Key', 'Keyboard Key']])
        self.store.get(STORE_KEYS.MIDI_KEY_MAP).extend(key_map)
        self.store.put(STORE_KEYS.CONFIGURING_KEY_MAP, True)

    def init_control_flags(self):
        self.control_flags[CONTROL_FLAGS.WAITING_FOR_MIDI_INPUT] = False
        self.control_flags[CONTROL_FLAGS.WAITING_FOR_KEYBOARD_INPUT] = False

    def process_events(self, event):
        manager = self.display_controller.get_manager()
        manager.process_events(event)


class Store:
    def __init__(self):
        self.storage = {}

    def get(self, key):
        if key not in self.storage.keys():
            return None
        return self.storage[key]

    def put(self, key, value):
        self.storage[key] = value


class input_controller:
    def __init__(self, game_ctrl, midi_input, device_id):
        self.input_midi_queue = InputMidiQueue(game_ctrl, midi_input, device_id)
        self.input_ui_queue = InputUIEventQueue(game_ctrl)
        self.input_keyboard_queue = InputKeyboardEventQueue(game_ctrl)

    def start(self):
        self.input_midi_queue.start()
        self.input_ui_queue.start()
        self.input_keyboard_queue.start()

    def close(self):
        self.input_midi_queue.quit()
        self.input_ui_queue.quit()
        self.input_keyboard_queue.quit()
