import sys

import pygame
from pygame import midi as pygame_midi
from rtmidi import midiutil

from MidiControl import MidiControl
from PygameControl import game_controller, input_controller

game_ctrl = game_controller()
midiutil.list_input_ports()
device_id = int(input('Select MIDI input port (Control-C to exit):')) + 1
midiutil.open_midiinput(device_id)

game_ctrl.store.put('midi_devices', MidiControl.get_input_midi_devices())

game_ctrl.start()

painter = game_ctrl.painter
painter.draw_ui()

device_info = [pygame_midi.get_device_info(i) for i in range(pygame_midi.get_count())]
print('Please press any key to locate your device.')

midi_input = pygame_midi.Input(device_id)
input_controller = input_controller(game_ctrl, midi_input, device_id)

print("Using input #{}".format(device_info[device_id]))

input_controller.start()

clock = pygame.time.Clock()
is_running = True

while is_running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            is_running = False
        if event.type == pygame.KEYDOWN:
            input_controller.input_keyboard_queue.accept(event)
        if event.type == pygame.USEREVENT:
            input_controller.input_ui_queue.accept(event)
        game_ctrl.process_events(event)

    game_ctrl.display_controller.handle_frame(clock.tick(60) / 1000.0)
    pygame.display.update()

input_controller.close()
pygame.quit()
sys.exit()
