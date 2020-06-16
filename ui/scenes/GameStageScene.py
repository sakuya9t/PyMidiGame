from KeyMapper import get_midi_key_code, is_black_key
from constants import COLORS
from controllers.SceneController import SceneController
from midi import MidiInfo, Note
from ui.scenes import Scene

GAME_BOARD_WIDTH = 924
GAME_BOARD_LEFT_POS = 50
GAME_BOARD_BASE_LINE_Y_POS = 670
NOTE_BEFORE_HIT_REGION_HEIGHT = 600
NOTE_AFTER_HIT_REGION_HEIGHT = 50
KEY_COUNT = 32
BEAT_LENGTH_IN_PX = 20
LOWEST_KEY = 'C3'
HIGHEST_KEY = 'G4'


# deprecated as 3d scene introduced.
class GameStageScene(Scene):
    def __init__(self, painter):
        super(GameStageScene, self).__init__(painter)
        self.scene_controller = SceneController()
        self.midi_info = MidiInfo('resources/平和な日々.mid')
        self.scene_controller.start_stopwatch()
        self.notes = self.midi_info.to_note_list()
        self.curr_beat = 0  # current playing process indicator

    def render(self):
        self.painter.clear_screen()
        self.__set_curr_beat__()
        self.painter.print_word(str(self.scene_controller.time_elapsed_stopwatch()), (0, 0))
        self.draw_board()
        for note in self.notes:
            self.draw_note(note)

    def draw_board(self):
        # base line
        self.painter.draw_line((GAME_BOARD_LEFT_POS, GAME_BOARD_BASE_LINE_Y_POS),
                               (GAME_BOARD_LEFT_POS + GAME_BOARD_WIDTH, GAME_BOARD_BASE_LINE_Y_POS),
                               color=(155, 242, 39), line_width=2)
        # draw tracks
        track_width = GAME_BOARD_WIDTH / KEY_COUNT
        for i in range(KEY_COUNT + 1):
            self.painter.draw_line((GAME_BOARD_LEFT_POS + track_width * i,
                                    GAME_BOARD_BASE_LINE_Y_POS - NOTE_BEFORE_HIT_REGION_HEIGHT),
                                   (GAME_BOARD_LEFT_POS + track_width * i,
                                    GAME_BOARD_BASE_LINE_Y_POS + NOTE_AFTER_HIT_REGION_HEIGHT),
                                   color=COLORS.GRAY_12)
        # draw bar lines
        beats_per_bar = self.midi_info.time_signature.numerator
        bar_line_beat_ids = __get_bar_line_beat_ids__(beats_per_bar, self.curr_beat,
                                                      NOTE_BEFORE_HIT_REGION_HEIGHT // BEAT_LENGTH_IN_PX)
        for bar_line_beat_id in bar_line_beat_ids:
            self.painter.draw_line((GAME_BOARD_LEFT_POS, GAME_BOARD_BASE_LINE_Y_POS - (bar_line_beat_id - self.curr_beat) * BEAT_LENGTH_IN_PX),
                                   (GAME_BOARD_LEFT_POS + GAME_BOARD_WIDTH, GAME_BOARD_BASE_LINE_Y_POS - (bar_line_beat_id - self.curr_beat) * BEAT_LENGTH_IN_PX),
                                   color=COLORS.GRAY_6)

    def draw_note(self, note: Note):
        track_id = get_midi_key_code(note.note_name) - get_midi_key_code(LOWEST_KEY)
        note_position = (note.start - self.curr_beat) * BEAT_LENGTH_IN_PX
        if (not 0 <= track_id < KEY_COUNT) or note_position > NOTE_BEFORE_HIT_REGION_HEIGHT:
            return
        note_width = BEAT_LENGTH_IN_PX * note.duration
        if note_position < 0:
            note_width += note_position
            note_position = 0
            if note_width < 0:
                return
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

    def __set_curr_beat__(self):
        timestamp_in_minute = self.scene_controller.time_elapsed_stopwatch() / 1000 / 60
        bpm = self.midi_info.bpm
        self.curr_beat = timestamp_in_minute * bpm


def __get_bar_line_beat_ids__(beats_per_bar, curr_beat, beat_range):
    res = []
    for b in range(int(curr_beat) // beats_per_bar, (int(curr_beat) + beat_range) // beats_per_bar + 1):
        if curr_beat <= b * beats_per_bar <= curr_beat + beat_range:
            res.append(b * beats_per_bar)
    return res
