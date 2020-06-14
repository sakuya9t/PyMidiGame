import sys
import pygame

from controllers.GameController import GameController

game_ctrl = GameController()
game_ctrl.start()

input_controller = game_ctrl.input_controller

painter = game_ctrl.painter
painter.draw_ui()

is_running = True

while is_running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            is_running = False
        game_ctrl.process_events(event)
    game_ctrl.handle_frame()

pygame.quit()
game_ctrl.quit()
sys.exit()

