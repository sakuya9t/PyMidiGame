import sys
import pygame

from controllers.GameController import GameController

game_ctrl = GameController()
game_ctrl.start()

input_controller = game_ctrl.input_controller

painter = game_ctrl.painter
painter.draw_ui()

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
    pygame.display.flip()

input_controller.close()
pygame.quit()
game_ctrl.quit()
sys.exit()

