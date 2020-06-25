import math
from datetime import datetime

import pygame as pg

from OpenGL.GL import *
from OpenGL.GLU import *

# constants
from KeyMapper import get_midi_key_code
from constants import UI_CONSTANT
from midi import Note, MidiInfo

key_count = 32
LOWEST_KEY = 'C3'

# game_board_specs
game_board_left = -3
game_board_top = -15
game_board_right = 3
game_board_bottom = 5
game_board_width = 6
game_board_height = 20

game_board_before_key_height = 19.5
game_board_after_key_height = 0.5

# colors
black = (0, 0, 0, 0.5)
green = (0, 1, 0)
white = (1, 1, 1)
pink = (0.8, 0.6, 0.6, 1)
grey = (0.5, 0.5, 0.5, 1)
grey_75 = (0.25, 0.25, 0.25, 0.75)
grey_25 = (0.75, 0.75, 0.75, 0.75)
grey_5 = (0.95, 0.95, 0.95, 0.75)
transparent = (1, 1, 1, 0)


def draw_square():
    """
    Draws a square.
    """

    # sets the color of the square
    glColor3f(*green)

    # draws the square
    # down and right are positive.
    glRectf(-0.3, 0, 0, -0.3)


def draw_circle(radius, center: (float, float, float), filled=True, side_num=360, color=white):
    glPushMatrix()
    x, y, z = center
    glTranslatef(x, y, z)
    glLineWidth(1)
    if filled:
        glBegin(GL_POLYGON)
    else:
        glBegin(GL_LINE_LOOP)
    glColor(*color)
    for vertex in range(0, side_num):
        angle = float(vertex) * 2.0 * math.pi / side_num
        glVertex3f(math.cos(angle) * radius, math.sin(angle) * radius, 0.0)
    glEnd()
    glPopMatrix()


def draw_rounded_rectangle(left, top, right, bottom, radius, color=white, filled=True):
    def draw_rounded_cornet(x, y, sa, arc, r):
        cent_x = x + r * math.cos(sa + math.pi / 2)
        cent_y = y + r * math.sin(sa + math.pi / 2)
        n = math.ceil(90 * arc / math.pi * 2)
        for i in range(0, n + 1):
            ang = sa + arc * i / n
            next_x = cent_x + r * math.sin(ang)
            next_y = cent_y - r * math.cos(ang)
            glVertex3f(next_x, next_y, 0.0)

    if left > right:
        left, right = right, left
    if top > bottom:
        top, bottom = bottom, top
    if filled:
        glBegin(GL_POLYGON)
    else:
        glBegin(GL_LINE_LOOP)
    glColor(*color)
    draw_rounded_cornet(left, top + radius, 3 * math.pi / 2, math.pi / 2, radius)  # top-left
    draw_rounded_cornet(right - radius, top, 0.0, math.pi / 2, radius)  # top-right
    draw_rounded_cornet(right, bottom - radius, math.pi / 2, math.pi / 2, radius)  # bottom-right
    draw_rounded_cornet(left + radius, bottom, math.pi, math.pi / 2, radius)  # bottom-left
    glEnd()


def draw_wire_cube():
    edges = ((0, 1), (0, 3), (0, 4), (1, 2), (1, 7), (2, 5), (2, 3), (3, 6), (4, 6), (4, 7), (5, 6), (5, 7))
    vertices = (
        (3, 0.1, 5), (3, 0.1, -10), (3, 0, -10), (3, 0, 5), (-3, 0.1, 5), (-3, 0, -10), (-3, 0, 5), (-3, 0.1, -10))
    glColor3f(*pink)
    glBegin(GL_LINES)
    for cubeEdge in edges:
        for cubeVertex in cubeEdge:
            glVertex3fv(vertices[cubeVertex])
    glEnd()


def draw_game_outer_surface():
    vertices = (
        (game_board_right, 0, game_board_bottom),
        (game_board_right, 0, game_board_top),
        (game_board_right, -0.1, game_board_top),
        (game_board_right, -0.1, game_board_bottom),
        (game_board_left, 0, game_board_bottom),
        (game_board_left, -0.1, game_board_top),
        (game_board_left, -0.1, game_board_bottom),
        (game_board_left, 0, game_board_top))
    surfaces = ({'v': (0, 3, 6, 4), 'color': grey_25},
                {'v': (2, 5, 6, 3), 'color': grey_25},
                {'v': (1, 2, 5, 7), 'color': grey_25},
                {'v': (7, 4, 6, 5), 'color': grey_25},
                {'v': (2, 3, 0, 1), 'color': grey_25},
                {'v': (1, 0, 4, 7), 'color': grey_75})
    glBegin(GL_QUADS)
    for cubeQuad in surfaces:
        glColor(*cubeQuad['color'])
        for cubeVertex in cubeQuad['v']:
            glVertex3fv(vertices[cubeVertex])
    glEnd()
    draw_key_bars()


def draw_key_bars():
    track_width = game_board_width / key_count
    vertices = []
    track_y_pos = 0.01
    note_hit_height = game_board_bottom - game_board_after_key_height
    vertices_horizon = [(game_board_left, track_y_pos, note_hit_height),
                        (game_board_right, track_y_pos, note_hit_height)]
    for i in range(1, key_count):
        vertices.append((game_board_left + track_width * i, track_y_pos, game_board_top))
        vertices.append((game_board_left + track_width * i, track_y_pos, game_board_bottom))
    glColor(*grey_5)
    glLineWidth(0.5)
    glBegin(GL_LINES)
    for i in range(len(vertices)):
        glVertex3fv(vertices[i])
    glEnd()
    # note hit bar
    glLineWidth(5)
    glBegin(GL_LINES)
    for v in vertices_horizon:
        glVertex3fv(v)
    glEnd()
    glLineWidth(1)  # reset line width


def draw_note(note: Note, speed=1.0):
    note_length = note.duration * speed
    note_position = note.start * speed
    lane = get_midi_key_code(note.note_name) - get_midi_key_code(LOWEST_KEY)
    track_width = game_board_width / key_count
    # fixme: display issue when note is longer than game board (e.g. when speed=5)
    note_length = min(note_length,
                      note_position + note_length + game_board_after_key_height,  # near bound
                      game_board_before_key_height - note_position)  # far bound
    if note_length < 0:
        return
    offset_before_scale = (0, 0, -note_length)  # set note position according to their bottom (closest to player)
    scale = (track_width, 0.2, 1)  # what does 1 means in each direction
    note_position = max(note_position, -game_board_after_key_height)
    offset = (game_board_left + lane * track_width,
              0,
              game_board_bottom - game_board_after_key_height - note_position)
    slope_in = min(note_length, 0.05)
    slope_out = max(0.0, note_length - 0.05)
    vertices = [(0, 0, slope_in), (0, 0, slope_out), (0.2, 0, 0), (0.2, 0.2, slope_in),
                (0.2, 0.2, slope_out), (0.2, 0, note_length), (0.8, 0, 0), (0.8, 0.2, slope_in),
                (0.8, 0.2, slope_out), (0.8, 0, note_length), (1, 0, slope_in), (1, 0, slope_out)]
    vertices = [((v[0] + offset_before_scale[0]) * scale[0] + offset[0],
                 (v[1] + offset_before_scale[1]) * scale[1] + offset[1],
                 (v[2] + offset_before_scale[2]) * scale[2] + offset[2])
                for v in vertices]
    edges = [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5), (2, 3), (3, 4), (4, 5),
             (2, 6), (3, 7), (4, 8), (5, 9), (6, 7), (7, 8), (8, 9), (6, 10),
             (7, 10), (8, 11), (9, 11), (10, 11)]
    dark_pink = (0.4, 0.3, 0.3)
    lighter_pink = (0.5, 0.4, 0.4)
    slight_darker_pink = (0.375, 0.275, 0.275)
    darker_pink = (0.35, 0.25, 0.25)
    squares = [{'v': (0, 1, 4, 3), 'color': dark_pink},  # left
               {'v': (2, 3, 7, 6), 'color': slight_darker_pink},  # back
               {'v': (3, 4, 8, 7), 'color': lighter_pink},  # top
               {'v': (4, 5, 9, 8), 'color': slight_darker_pink},  # front
               {'v': (7, 8, 11, 10), 'color': dark_pink}]  # right
    triangles = [{'v': (0, 2, 3), 'color': dark_pink},  # top left
                 {'v': (1, 4, 5), 'color': darker_pink},  # bottom left
                 {'v': (6, 7, 10), 'color': dark_pink},  # top right
                 {'v': (8, 9, 11), 'color': darker_pink}]  # bottom right
    glPushMatrix()
    material_color = (1, 1, 1, 0)
    glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE, material_color)
    glBegin(GL_QUADS)
    for quad in squares:
        glColor(*quad['color'])
        for cubeVertex in quad['v']:
            glVertex3fv(vertices[cubeVertex])
    glEnd()
    glBegin(GL_TRIANGLES)
    for tri in triangles:
        glColor(*tri['color'])
        for cubeVertex in tri['v']:
            glVertex3fv(vertices[cubeVertex])
    glEnd()
    glPopMatrix()


def draw_notes(notes, offset, speed=1.5):
    notes = [x for x in notes if offset <= x.start * speed <= game_board_before_key_height - speed * offset]
    for note in notes:
        n = Note(note.start + offset, note.duration, note.note_name)
        draw_note(n, speed)


def draw_text(position: (float, float, float), text: str):
    font = pg.font.Font(None, 24)
    text_surface = font.render(text, True, (255, 255, 255, 1))
    text_data = pg.image.tostring(text_surface, "RGBA", True)
    glRasterPos3d(*position)
    glDrawPixels(text_surface.get_width(), text_surface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)


def draw_press_effect(note_name: str):
    effect_length = 3
    lane = get_midi_key_code(note_name) - get_midi_key_code(LOWEST_KEY)
    track_width = game_board_width / key_count
    points = [(game_board_left + track_width, 0, game_board_bottom - effect_length),
              (game_board_left, 0, game_board_bottom - effect_length),
              (game_board_left, 0, game_board_bottom),
              (game_board_left + track_width, 0, game_board_bottom)]
    points = [(x[0] + lane * track_width, x[1], x[2]) for x in points]
    colors = [transparent, transparent, white, white]
    glBegin(GL_QUADS)
    for i in range(4):
        glColor(*colors[i])
        glVertex3fv(points[i])
    glEnd()


def resize(width, height):
    """
    Updates the viewport when the screen is resized.
    """

    # sets the viewport
    glViewport(0, 0, width, height)

    # sets the model view
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


def init():
    display = UI_CONSTANT.SCREEN_SIZE
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -10)

    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_BLEND)
    glColorMaterial(GL_FRONT, GL_AMBIENT_AND_DIFFUSE)


def main():
    pg.init()
    state = 0
    note_offset = 0
    pg.display.set_mode(UI_CONSTANT.SCREEN_SIZE, pg.DOUBLEBUF | pg.OPENGL)
    midi_info = MidiInfo('../../resources/平和な日々.mid')
    notes = midi_info.to_note_list()
    pressed_notes = ['F3', 'D#4']
    print(len(notes))
    init()

    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                quit()

            elif event.type == pg.KEYDOWN:
                if state == 0:
                    pg.display.set_mode(UI_CONSTANT.SCREEN_SIZE, 0)
                else:
                    pg.display.set_mode(UI_CONSTANT.SCREEN_SIZE, pg.DOUBLEBUF | pg.OPENGL)
                    init()
                state = 1 - state

        if state == 0:
            glPushMatrix()
            glTranslatef(0, 0, 4)
            glLight(GL_LIGHT0, GL_POSITION, (0, 2, 1, 2))
            glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.6, 0.6, 0.6, 1))
            glLightfv(GL_LIGHT0, GL_AMBIENT, (1, 1, 1, 0.5))
            glPopMatrix()
            note_offset -= 0.05
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            # draw game board
            glPushMatrix()
            glTranslatef(0, 0.8, 0)
            glRotatef(30, 1, 0, 0)
            draw_game_outer_surface()
            draw_notes(notes, note_offset)
            for pressed_note in pressed_notes:
                draw_press_effect(pressed_note)
            glPopMatrix()
            # draw game board end
            glPushMatrix()
            glTranslatef(-5.3, 3.8, 0)
            draw_text((0, 0, 0), datetime.now().strftime("%H:%M:%S.%f'")[:-3])
            glPopMatrix()
        pg.display.flip()
        pg.time.wait(10)


if __name__ == '__main__':
    main()
