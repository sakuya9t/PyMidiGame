import threading
import json
from queue import Queue

import pygame
import pygame_gui

from KeyCodeConstants import get_pyautogui_key_name
from KeyMapper import KeyMapper
from constants import UI_CONSTANT, CONTROL_FLAGS, STORE_KEYS, CONFIG_KEYS
from midis2events import midis2events, simplify_midi_event


class InputQueue(threading.Thread):
    def __init__(self):
        super(InputQueue, self).__init__()
        self.running = True

    def quit(self):
        self.running = False


class InputMidiQueue(InputQueue):
    def __init__(self, game_controller, midi_input, midi_device):
        super(InputMidiQueue, self).__init__()
        self.buffer = Queue()
        self.display_controller = game_controller.display_controller
        self.midi_input = midi_input
        self.midi_device = midi_device
        self.key_mapper = KeyMapper()
        self.game_controller = game_controller
        self.control_flags = game_controller.control_flags

    def run(self):
        while self.running:
            if not self.midi_input.poll():
                continue

            events = midis2events(self.midi_input.read(40), self.midi_device)
            events = [simplify_midi_event(e) for e in events]
            print(events)
            if CONTROL_FLAGS.WAITING_FOR_MIDI_INPUT in self.control_flags.keys() and self.control_flags[CONTROL_FLAGS.WAITING_FOR_MIDI_INPUT]:
                self.control_flags[CONTROL_FLAGS.WAITING_FOR_MIDI_INPUT] = False
                self.control_flags[CONTROL_FLAGS.WAITING_FOR_KEYBOARD_INPUT] = True
                self.game_controller.store.put('midi_key_pressed', events[0]['id'])
                self.game_controller.store.put(STORE_KEYS.MIDI_INPUT_INDICATOR, UI_CONSTANT.MESSAGE_WAIT_FOR_KEYBOARD_INPUT)
                self.display_controller.refresh()
            self.key_mapper.map_midi(events)
        self.midi_input.close()


class InputUIEventQueue(InputQueue):
    def __init__(self, game_controller):
        super(InputUIEventQueue, self).__init__()
        self.buffer = Queue()
        self.game_controller = game_controller
        self.ui_control = game_controller.ui_control
        self.painter = game_controller.painter
        self.control_flags = game_controller.control_flags
        self.display_controller = game_controller.display_controller

    def run(self):
        while self.running:
            if not self.buffer.empty():
                event = self.buffer.get()
                if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    object_id = str.split(event.ui_object_id, '.')[-1]
                    if object_id == UI_CONSTANT.ID_OK_BTN:
                        key_map_settings = self.game_controller.store.get(STORE_KEYS.MIDI_KEY_MAP)[1:]
                        # todo: map back to pyautogui keymap
                        key_map_settings = {x[0]: get_pyautogui_key_name(pygame.key.key_code(x[1])) for x in key_map_settings}
                        self.game_controller.config.set(CONFIG_KEYS.MIDI_MAPPING, key_map_settings)
                        self.game_controller.store.put(STORE_KEYS.CONFIGURING_KEY_MAP, False)
                        self.display_controller.refresh()
                    elif object_id == UI_CONSTANT.ID_CANCEL_BTN:
                        print('cancel clicked')
                    elif object_id == UI_CONSTANT.ID_MIDI_MAP_KEY_BTN:
                        self.ui_control[UI_CONSTANT.KEY_POPUP] = True
                        self.display_controller.refresh()
                        self.control_flags[CONTROL_FLAGS.WAITING_FOR_MIDI_INPUT] = True
                        print('map midi key')
                    print(event)
                elif event.user_type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
                    print('{} selected {}.'.format(event.ui_object_id, event.text))
                print(event)

    def accept(self, event):
        self.buffer.put(event)


class InputKeyboardEventQueue(InputQueue):
    def __init__(self, game_controller):
        super(InputKeyboardEventQueue, self).__init__()
        self.buffer = Queue()
        self.game_controller = game_controller
        self.control_flags = game_controller.control_flags
        self.ui_control = game_controller.ui_control
        self.display_controller = game_controller.display_controller

    def run(self):
        while self.running:
            if not self.buffer.empty():
                event = self.buffer.get()
                print(event.key)
                if self.control_flags[CONTROL_FLAGS.WAITING_FOR_KEYBOARD_INPUT]:
                    self.control_flags[CONTROL_FLAGS.WAITING_FOR_KEYBOARD_INPUT] = False
                    self.game_controller.store.put(STORE_KEYS.MIDI_INPUT_INDICATOR, UI_CONSTANT.MESSAGE_WAIT_FOR_MIDI_INPUT)
                    self.ui_control[UI_CONSTANT.KEY_POPUP] = False
                    self.display_controller.refresh()
                    midi_key = self.game_controller.store.get('midi_key_pressed')
                    self.game_controller.store.get(STORE_KEYS.MIDI_KEY_MAP).append([midi_key, pygame.key.name(event.key)])
                    self.game_controller.store.put('midi_key_pressed', None)

    def accept(self, event):
        self.buffer.put(event)
