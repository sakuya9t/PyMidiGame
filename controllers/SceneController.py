import time

from constants import SCENE_PARAMETER
from controllers import Controller


class SceneController(Controller):
    def __init__(self):
        super(SceneController, self).__init__()

    def init_store(self):
        self.store.put(SCENE_PARAMETER.TIMESTAMP, 0)

    def start_stopwatch(self):
        self.store.put(SCENE_PARAMETER.START_TIMESTAMP, int(round(time.time() * 1000)))

    def reset_stopwatch(self):
        self.store.put(SCENE_PARAMETER.START_TIMESTAMP, 0)

    def time_elapsed_stopwatch(self):
        start_timestamp = self.store.get(SCENE_PARAMETER.START_TIMESTAMP)
        if not start_timestamp:
            return 0
        return int(round(time.time() * 1000.0)) - start_timestamp
