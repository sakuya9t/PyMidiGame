from ui.scenes.GameStageScene import GameStageScene


class GameDisplay:
    def __init__(self, painter, should_render):
        self.painter = painter
        self.should_render = should_render
        self.game_stage_scene = GameStageScene(self.painter)

    def render(self):
        if self.should_render():
            self.game_stage_scene.render()
