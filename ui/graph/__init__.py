# coding=utf-8

# imports the Pygame library
import pygame as pg

# imports the GL sub-module of the OpenGL module
# Note: PyOpenGL installation is required
from OpenGL.GL import *
from OpenGL.GLU import *

# colors
black = (0, 0, 0, 1)
green = (0, 1, 0)
white = (1, 1, 1)
pink = (0.8, 0.6, 0.6)


cubeVertices = ((1,1,1),(1,1,-1),(1,-1,-1),(1,-1,1),(-1,1,1),(-1,-1,-1),(-1,-1,1),(-1,1,-1))
cubeEdges = ((0,1),(0,3),(0,4),(1,2),(1,7),(2,5),(2,3),(3,6),(4,6),(4,7),(5,6),(5,7))
cubeQuads = ((0,3,6,4),(2,5,6,3),(1,2,5,7),(1,0,4,7),(7,4,6,5),(2,3,0,1))


def draw_square():
    """
    Draws a square.
    """

    # cleans the background
    glClear(GL_COLOR_BUFFER_BIT)

    # sets the color of the square
    glColor3f(*green)

    # draws the square
    # down and right are positive.
    glRectf(-0.3, 0, 0, -0.3)

def wireCube():
    glColor3f(*pink)
    glBegin(GL_LINES)
    for cubeEdge in cubeEdges:
        for cubeVertex in cubeEdge:
            glVertex3fv(cubeVertices[cubeVertex])
    glEnd()

def solidCube():
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
            # solidCube()
            glPushMatrix()
            glRotatef(deg, 0, 1, 0)
            glTranslatef(0.15, 0.15, 0)
            draw_square()
            glPopMatrix()
            glPushMatrix()
            glRotatef(deg, 1, 0, 0)
            wireCube()
            glPopMatrix()
        pg.display.flip()
        pg.time.wait(10)


if __name__ == '__main__':
    main()
