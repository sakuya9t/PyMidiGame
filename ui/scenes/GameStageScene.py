from datetime import datetime

from KeyMapper import get_midi_key_code, is_black_key
from constants import COLORS
from controllers.SceneController import SceneController
from ui.scenes import Scene

game_window_width = 700


class GameStageScene(Scene):
    def __init__(self, painter):
        super(GameStageScene, self).__init__(painter)
        self.scene_controller = SceneController()
        # self.scene_controller.start_stopwatch()
        self.notes = [Note(10, 20, 'C3'), Note(25, 1, 'F#4'), Note(30, 1, 'A3')]

    def render(self):
        self.painter.print_word(str(self.scene_controller.time_elapsed_stopwatch()), (0, 0))
        self.painter.draw_line((50, 500), (750, 500), color=(155, 242, 39), line_width=2)
        track_width = game_window_width / 32
        for i in range(33):
            self.painter.draw_line((50+track_width*i, 100), (50+track_width*i, 525), color=COLORS.GRAY_25)

        for note in self.notes:
            self.draw_note(note)

    def draw_note(self, note):
        track_id = get_midi_key_code(note.note_name) - get_midi_key_code('C3')
        note_position = note.start * 5
        note_width = 5 * note.duration
        self.__draw_note__(track_id, note_position, is_black_key(note.note_name), note_width)

    def __draw_note__(self, track_id, note_position, is_black_key, note_width=5):
        """
        Draw a note calling pygame library.
        :param track_id: Which track to display the given note.
        :param note_position: Distance from note bottom to base line..
        :param note_width: Indicates length of a note.
        :return: None
        """
        track_width = game_window_width / 32
        track_line_left = 51 + track_id * track_width
        color = COLORS.PINK if is_black_key else COLORS.GRAY_50
        self.painter.draw_rect(track_line_left, 500 - note_position - note_width, track_width - 1, note_width, color)


class Note:
    def __init__(self, start, duration, note_name):
        self.start = start
        self.duration = duration
        self.note_name = note_name
