from controllers.SceneController import SceneController


class Scene:
    def __init__(self, painter):
        self.painter = painter
        self.scene_controller = SceneController()
