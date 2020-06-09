from config.Config import Config
from constants import STORE_KEYS
from ui.Component import Component
from ui.ConfigBox import ConfigBox


class UI:
    def __init__(self, ui_manager, store, ui_control):
        self.config = Config('ui/ui_layout.json')
        self.manager = ui_manager
        self.store = store
        self.controller = ui_control

    def render(self):
        ConfigBox(ui=self, should_render=self.store.get(STORE_KEYS.CONFIGURING_KEY_MAP)).render()


class GameDisplay(Component):
    def render(self):
        pass
