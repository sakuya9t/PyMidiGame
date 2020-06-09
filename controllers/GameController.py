import pygame

from KeyCodeConstants import get_key_code
from MidiControl import MidiControl
from PygameControl import InputController
from config.Config import Config
from constants import CONFIG_KEYS, STORE_KEYS, CONTROL_FLAGS, UI_CONSTANT
from controllers import Controller
from logger import logger
from settings.MidiDeviceSettings import MidiDeviceSettings
from pygame import midi as pygame_midi

from window import window_control, window_painter

config = Config('config/config.json')
key_name = config.get(CONFIG_KEYS.MIDI_KEY)


class GameController(Controller):
    def __init__(self):
        pygame.init()
        self.config = config
        self.font = None
        self.ui_control = {}
        super(GameController, self).__init__()
        self.display_controller = None
        self.painter = None
        self.control_flags = {}
        self.init_control_flags()
        self.logger = logger()
        self.midi_device_settings = MidiDeviceSettings()
        self.input_controller = None

    def start(self):
        pygame.font.init()
        self.font = pygame.font.SysFont(None, 24)
        pygame_midi.init()
        self.logger.start()
        self.display_controller = window_control(self.ui_control)
        self.painter = window_painter(self.display_controller, self.font, self.store)
        self.display_controller.init(painter=self.painter, store=self.store)
        self.input_controller = InputController(self)
        self.input_controller.start()
        self.__init_midi_device__()

    def __init_midi_device__(self):
        device_id = self.store.get(STORE_KEYS.SELECTED_MIDI_DEVICE)
        self.input_controller.set_midi_input(device_id)

    def init_store(self):
        configed_key_map = config.get(CONFIG_KEYS.MIDI_MAPPING)
        key_map = [[key, pygame.key.name(get_key_code(value))] for key, value in configed_key_map.items()]
        self.store.put(STORE_KEYS.MIDI_INPUT_INDICATOR, UI_CONSTANT.MESSAGE_WAIT_FOR_MIDI_INPUT)
        self.store.put(STORE_KEYS.MIDI_KEY_MAP, [['MIDI Key', 'Keyboard Key']])
        self.store.get(STORE_KEYS.MIDI_KEY_MAP).extend(key_map)
        self.store.put(STORE_KEYS.CONFIGURING_KEY_MAP, False)  # whether displaying the config dialog.
        self.store.put(STORE_KEYS.MIDI_DEVICES, [''] + MidiControl.get_input_midi_devices())
        self.store.put(STORE_KEYS.SELECTED_MIDI_DEVICE, self.config.get(CONFIG_KEYS.MIDI_DEVICE_ID))

    def init_control_flags(self):
        self.control_flags[CONTROL_FLAGS.WAITING_FOR_MIDI_INPUT] = False
        self.control_flags[CONTROL_FLAGS.WAITING_FOR_KEYBOARD_INPUT] = False

    def process_events(self, event):
        manager = self.display_controller.get_manager()
        manager.process_events(event)

    def quit(self):
        self.logger.exit()