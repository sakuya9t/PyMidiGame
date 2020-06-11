import math

import pygame as pg

from OpenGL.GL import *
from OpenGL.GLU import *

# colors
black = (0, 0, 0, 1)
green = (0, 1, 0)
white = (1, 1, 1)
pink = (0.8, 0.6, 0.6)
grey = (0.5, 0.5, 0.5, 0.5)


cubeVertices = ((1,1,1),(1,1,-1),(1,-1,-1),(1,-1,1),(-1,1,1),(-1,-1,-1),(-1,-1,1),(-1,1,-1))
cubeEdges = ((0,1),(0,3),(0,4),(1,2),(1,7),(2,5),(2,3),(3,6),(4,6),(4,7),(5,6),(5,7))
cubeQuads = ((0,3,6,4),(2,5,6,3),(1,2,5,7),(1,0,4,7),(7,4,6,5),(2,3,0,1))


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
        for i in range(0, n+1):
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
    glColor3f(*pink)
    glBegin(GL_LINES)
    for cubeEdge in cubeEdges:
        for cubeVertex in cubeEdge:
            glVertex3fv(cubeVertices[cubeVertex])
    glEnd()


def draw_solid_cube():
    glColor3f(*white)
    glBegin(GL_QUADS)
    for cubeQuad in cubeQuads:
        for cubeVertex in cubeQuad:
            glVertex3fv(cubeVertices[cubeVertex])
    glEnd()


def init():
    display = (1024, 768)
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -10)


def resize(width, height):
    """
    Updates the viewport when the screen is resized.
    """

    # sets the viewport
    glViewport(0, 0, width, height)

    # sets the model view
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


def main():
    pg.init()
    display = (1024, 768)
    state = 0
    deg = 0
    pg.display.set_mode(display, pg.DOUBLEBUF | pg.OPENGL)
    init()

    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                quit()

            elif event.type == pg.KEYDOWN:
                pg.display.quit()
                pg.display.init()
                if state == 0:
                    pg.display.set_mode(display, 0)
                else:
                    pg.display.set_mode(display, pg.DOUBLEBUF | pg.OPENGL)
                    init()
                state = 1 - state

        if state == 0:
            deg = (deg + 1) % 360
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            draw_circle(1, (1, 1, -10), filled=False, color=grey)
            glPushMatrix()
            glRotatef(deg, 1, 0, 0)
            draw_wire_cube()
            glPopMatrix()
            glPushMatrix()
            glRotatef(deg, 0, 1, 0)
            glTranslatef(0.15, 0.15, 0)
            draw_square()
            glPopMatrix()
            draw_rounded_rectangle(1, 0, -1, 1, 0.2, color=white, filled=False)
        pg.display.flip()
        pg.time.wait(10)


if __name__ == '__main__':
    main()
