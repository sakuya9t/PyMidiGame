from pygame import midi as pygame_midi

from InputQueue import InputMidiQueue, InputUIEventQueue, InputKeyboardEventQueue
from constants import STORE_KEYS, CONFIG_KEYS


class InputController:
    def __init__(self, game_ctrl):
        self.midi_input = game_ctrl.midi_device_settings.midi_input
        self.game_ctrl = game_ctrl
        device_id = game_ctrl.config.get(CONFIG_KEYS.MIDI_DEVICE_ID)
        self.input_midi_queue = InputMidiQueue(game_ctrl, self.midi_input, device_id)
        self.input_ui_queue = InputUIEventQueue(game_ctrl)
        self.input_keyboard_queue = InputKeyboardEventQueue(game_ctrl)
        self.logger = game_ctrl.logger

    def set_midi_input(self, device_id):
        old_device_id = self.game_ctrl.store.get(STORE_KEYS.SELECTED_MIDI_DEVICE)
        try:
            if self.input_midi_queue.is_alive():
                self.input_midi_queue.quit()
            if not device_id:
                self.midi_input = None
                return
            midi_input = pygame_midi.Input(device_id)
            if midi_input is not None:
                self.midi_input = midi_input
                self.input_midi_queue = InputMidiQueue(self.game_ctrl, self.midi_input, device_id)
                self.input_midi_queue.start()
        except Exception as e:
            self.logger.warning('Invalid midi device. Error: {}'.format(e))
            try:
                self.set_midi_input(old_device_id)
            except Exception:
                self.logger.warning('Cannot initialize midi device {}'.format(old_device_id))
                self.set_midi_input(None)

    def start(self):
        if self.midi_input is not None:
            self.input_midi_queue.start()
        self.input_ui_queue.start()
        self.input_keyboard_queue.start()

    def close(self):
        if self.input_midi_queue.is_alive():
            self.input_midi_queue.quit()
        self.input_ui_queue.quit()
        self.input_keyboard_queue.quit()
