import time

import pygame
import pygame_gui
from pygame import display

from constants import STORE_KEYS, COLORS, UI_CONSTANT
from ui.GameDisplay import GameDisplay
from ui.UI import UI


class window_control:
    def __init__(self, ui_control, window_size=UI_CONSTANT.SCREEN_SIZE):
        self.window_size = window_size
        self.__screen__ = display.set_mode(self.window_size)
        self.__surface__ = pygame.Surface(self.window_size)
        self.__manager__ = pygame_gui.UIManager(window_size)
        self.ui_control = ui_control
        self.game_display = None
        self.__refresh_flag__ = False
        self.painter = None
        self.store = None
        self.is_3d_scene = False

    def init(self, painter, store):
        self.painter = painter
        self.store = store
        self.game_display = GameDisplay(painter=self.painter,
                                        should_render=(lambda: not self.store.get(STORE_KEYS.CONFIGURING_KEY_MAP)))

    def switch_display(self):
        self.is_3d_scene = not self.is_3d_scene
        if self.is_3d_scene:
            pygame.display.set_mode(self.window_size, pygame.DOUBLEBUF | pygame.OPENGL)
        else:
            pygame.display.set_mode(self.window_size, 0)

    def get_screen(self):
        return self.__screen__

    def get_surface(self):
        return self.__surface__

    def get_manager(self):
        return self.__manager__

    def refresh(self):
        self.__refresh_flag__ = True

    def handle_frame(self, time_delta):
        if self.is_3d_scene:
            pygame.display.flip()
            return
        if self.__refresh_flag__:
            self.painter.refresh()
            self.__refresh_flag__ = False
        try:
            self.__manager__.update(time_delta)
            self.__screen__.blit(self.__surface__, (0, 0))
            self.__manager__.draw_ui(self.__screen__)
            self.game_display.render()
            pygame.display.flip()
        except Exception as e:
            print(e)
            # handle ui refresh timeout issue
            self.handle_frame(time_delta)


class window_painter:
    def __init__(self, controller, font, store):
        self.controller = controller
        self.surface = controller.get_surface()
        self.screen = controller.get_screen()
        self.manager = controller.get_manager()
        self.font = font
        self.ui_renderer = UI(self.manager, store, controller.ui_control)

    def clear_screen(self):
        self.surface.fill((0, 0, 0))

    def refresh(self):
        self.draw_ui()

    def draw_ui(self):
        self.manager.clear_and_reset()
        self.ui_renderer.render()

    def print_word(self, sentence, pos):
        text = self.font.render(sentence, True, COLORS.WHITE)
        text_rect = text.get_rect()
        (text_rect.top, text_rect.left) = pos
        self.screen.blit(text, text_rect)

    def draw_line(self, pos1, pos2, line_width=1, color=COLORS.WHITE):
        pygame.draw.line(self.surface, color, pos1, pos2, line_width)

    def draw_rect(self, left, top, width, height, color=COLORS.WHITE):
        rect = pygame.Rect(left, top, width, height)
        pygame.draw.rect(self.surface, color, rect)
