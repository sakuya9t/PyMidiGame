"""
src/ui/gl_overlay.py — composite a 2D pygame surface over the GL scene.

SurfacePresenter uploads a pygame surface (the menu, or the gameplay HUD) to a GL
texture and draws it as a screen-space, orthographic, alpha-blended fullscreen
quad on top of the 3D scene. This is the replacement for the legacy glDrawPixels
text path: all 2D UI is drawn with pygame (atlas materials, fonts) onto an
SRCALPHA surface, then presented here.
"""
from __future__ import annotations

import pygame
from OpenGL.GL import (
    GL_BLEND, GL_COLOR_BUFFER_BIT, GL_DEPTH_TEST, GL_MODELVIEW,
    GL_ONE_MINUS_SRC_ALPHA, GL_PROJECTION, GL_QUADS, GL_SRC_ALPHA,
    GL_TEXTURE_2D, glBegin, glBlendFunc, glColor4f, glDisable, glEnable, glEnd,
    glLoadIdentity, glMatrixMode, glPopMatrix, glPushMatrix, glTexCoord2f,
    glVertex2f,
)
from OpenGL.GLU import gluOrtho2D

from src.ui.gl_textures import SurfaceTexture


class SurfacePresenter:
    """Presents a full-window pygame surface as a textured quad over the GL scene."""

    def __init__(self, size: tuple[int, int]) -> None:
        self.width, self.height = size
        self._tex = SurfaceTexture()

    def present(self, surface: pygame.Surface) -> None:
        """Upload *surface* and draw it covering the window, upright, with alpha
        blending. Assumes a GL context for the window is current."""
        self._tex.update(surface)

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, self.width, 0, self.height)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)
        self._tex.bind()
        glColor4f(1.0, 1.0, 1.0, 1.0)

        # Surface uploaded flipped, so texel (0,0) is the image's bottom-left;
        # map it to the screen's bottom-left for an upright image.
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(self.width, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(self.width, self.height)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, self.height)
        glEnd()

        glDisable(GL_TEXTURE_2D)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glEnable(GL_DEPTH_TEST)
