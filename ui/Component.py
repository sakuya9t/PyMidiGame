class Component:
    def __init__(self, ui, should_render):
        self.config = ui.config
        self.manager = ui.manager
        self.store = ui.store
        self.controller = ui.controller
        self.should_render = should_render

    def render(self):
        pass
