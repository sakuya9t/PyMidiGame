import time

import pygame
import pygame_gui
from pygame import display

from ui.UI import UI


class window_control:
    def __init__(self, ui_control):
        self.window_size = (800, 600)
        self.__screen__ = display.set_mode(self.window_size)
        self.__surface__ = pygame.Surface(self.window_size)
        self.__manager__ = pygame_gui.UIManager((800, 600))
        self.ui_control = ui_control
        self.__refresh_flag__ = False
        self.painter = None
        display.flip()

    def get_screen(self):
        return self.__screen__

    def get_surface(self):
        return self.__surface__

    def get_manager(self):
        return self.__manager__

    def refresh(self):
        self.__refresh_flag__ = True

    def handle_frame(self, time_delta):
        if self.__refresh_flag__:
            self.painter.refresh()
            self.__refresh_flag__ = False
            display.flip()
        try:
            self.__manager__.update(time_delta)
            self.__screen__.blit(self.__surface__, (0, 0))
            self.__manager__.draw_ui(self.__screen__)
        except:
            # handle ui refresh timeout issue
            time.sleep(time_delta)
            self.handle_frame(time_delta)


class window_painter:
    colors = {'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255), 'darkBlue': (0, 0, 128),
              'white': (255, 255, 255), 'black': (0, 0, 0), 'pink': (255, 200, 200)}

    def __init__(self, controller, font, store):
        self.controller = controller
        self.screen = controller.get_screen()
        self.manager = controller.get_manager()
        self.font = font
        self.ui_renderer = UI(self.manager, store, controller.ui_control)

    def refresh(self):
        self.draw_ui()

    def draw_ui(self):
        self.manager.clear_and_reset()
        self.ui_renderer.render()

    def print_word(self, sentence, pos):
        text = self.font.render(sentence, True, self.colors['white'])
        text_rect = text.get_rect()
        (text_rect.top, text_rect.left) = pos
        self.screen.blit(text, text_rect)
        display.flip()
