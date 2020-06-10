from KeyMapper import get_midi_key_code, is_black_key
from constants import COLORS
from controllers.SceneController import SceneController
from midi import MidiInfo, Note
from ui.scenes import Scene

GAME_BOARD_WIDTH = 700
GAME_BOARD_LEFT_POS = 50
GAME_BOARD_BASE_LINE_Y_POS = 500
NOTE_BEFORE_HIT_REGION_HEIGHT = 400
NOTE_AFTER_HIT_REGION_HEIGHT = 25
KEY_COUNT = 32
LOWEST_KEY = 'C2'
HIGHEST_KEY = 'G3'


class GameStageScene(Scene):
    def __init__(self, painter):
        super(GameStageScene, self).__init__(painter)
        self.scene_controller = SceneController()
        self.midi_info = MidiInfo('resources/chords.mid')
        # self.scene_controller.start_stopwatch()
        self.notes = self.midi_info.to_note_list()

    def render(self):
        self.painter.print_word(str(self.scene_controller.time_elapsed_stopwatch()), (0, 0))
        self.painter.draw_line((GAME_BOARD_LEFT_POS, GAME_BOARD_BASE_LINE_Y_POS),
                               (GAME_BOARD_LEFT_POS + GAME_BOARD_WIDTH, GAME_BOARD_BASE_LINE_Y_POS),
                               color=(155, 242, 39), line_width=2)
        track_width = GAME_BOARD_WIDTH / KEY_COUNT
        for i in range(KEY_COUNT + 1):
            self.painter.draw_line((GAME_BOARD_LEFT_POS + track_width*i,
                                    GAME_BOARD_BASE_LINE_Y_POS - NOTE_BEFORE_HIT_REGION_HEIGHT),
                                   (GAME_BOARD_LEFT_POS + track_width*i,
                                    GAME_BOARD_BASE_LINE_Y_POS + NOTE_AFTER_HIT_REGION_HEIGHT),
                                   color=COLORS.GRAY_25)

        for note in self.notes:
            self.draw_note(note)

    def draw_note(self, note: Note):
        track_id = get_midi_key_code(note.note_name) - get_midi_key_code(LOWEST_KEY)
        note_position = note.start * .5
        if (not 0 <= track_id < KEY_COUNT) or note_position > NOTE_BEFORE_HIT_REGION_HEIGHT:
            return
        note_width = .5 * note.duration
        note_width = min(note_width, NOTE_BEFORE_HIT_REGION_HEIGHT - note_position)
        self.__draw_note__(track_id, note_position, is_black_key(note.note_name), note_width)

    def __draw_note__(self, track_id, note_position, is_black_key, note_width=5):
        """
        Draw a note calling pygame library.
        :param track_id: Which track to display the given note.
        :param note_position: Distance from note bottom to base line..
        :param note_width: Indicates length of a note.
        :return: None
        """
        track_width = GAME_BOARD_WIDTH / KEY_COUNT
        track_line_left = 51 + track_id * track_width
        color = COLORS.PINK if is_black_key else COLORS.GRAY_50
        self.painter.draw_rect(track_line_left, GAME_BOARD_BASE_LINE_Y_POS - note_position - note_width,
                               track_width - 1, note_width, color)
