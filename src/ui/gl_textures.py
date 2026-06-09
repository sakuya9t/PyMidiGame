"""
src/ui/gl_textures.py — pygame surface -> OpenGL texture bridges.

Two thin wrappers turn pygame imagery into GL textures:

- AtlasTexture: the static neon atlas (resources/ui/neon_texture_atlas.png),
  uploaded once and sampled by the 3D scene via the shared atlas UV table.
- SurfaceTexture: a dynamic surface (the menu / HUD overlay) re-uploaded each
  frame so it can be drawn as a textured quad over the GL scene.

Surfaces are uploaded flipped vertically to match OpenGL's bottom-left texture
origin, which is the convention atlas.uv() encodes. The GL *calls* require an
active context, but importing this module does not (PyOpenGL imports lazily), so
it is safe to import headlessly.
"""
from __future__ import annotations

import os

import pygame
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE, GL_LINEAR, GL_RGBA, GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T, GL_UNSIGNED_BYTE, glBindTexture, glGenTextures,
    glTexImage2D, glTexParameteri,
)

from src.ui import atlas as _atlas
from src.ui.atlas_surface import prepare_atlas_surface

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ATLAS = os.path.join(_ROOT, 'resources', 'ui', 'neon_texture_atlas.png')


def upload_surface(surface: pygame.Surface, tex_id: int | None = None) -> int:
    """Upload *surface* to a GL texture (creating one if *tex_id* is None) and
    return its id. The surface is flipped to GL's bottom-left origin."""
    width, height = surface.get_size()
    data = pygame.image.tostring(surface, 'RGBA', True)
    if tex_id is None:
        tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA,
                 GL_UNSIGNED_BYTE, data)
    return tex_id


class AtlasTexture:
    """The neon atlas as a static GL texture plus a uv() region lookup.

    Loading the image happens at construction (cheap, headless-safe); the GL
    upload is deferred to the first bind() so the object can be created before a
    GL context exists. `available` is False when the atlas image is missing, in
    which case callers fall back to flat-colored geometry."""

    def __init__(self, path: str = DEFAULT_ATLAS) -> None:
        self.path = path
        self._tex: int | None = None
        self._surface: pygame.Surface | None = None
        if os.path.exists(path):
            try:
                self._surface = prepare_atlas_surface(pygame.image.load(path))
            except pygame.error:
                self._surface = None

    @property
    def available(self) -> bool:
        return self._surface is not None

    def bind(self) -> None:
        """Bind the atlas texture, uploading it on first use. No-op (leaves no
        texture bound) when the atlas is unavailable."""
        if self._tex is None and self._surface is not None:
            self._tex = upload_surface(self._surface)
        if self._tex is not None:
            glBindTexture(GL_TEXTURE_2D, self._tex)

    def uv(self, family: str, name: str) -> _atlas.UV | None:
        return _atlas.uv(family, name)


class SurfaceTexture:
    """A dynamic pygame surface wrapped as a GL texture, re-uploaded on update()."""

    def __init__(self) -> None:
        self._tex: int | None = None
        self.size: tuple[int, int] | None = None

    def update(self, surface: pygame.Surface) -> None:
        self._tex = upload_surface(surface, self._tex)
        self.size = surface.get_size()

    def bind(self) -> None:
        if self._tex is not None:
            glBindTexture(GL_TEXTURE_2D, self._tex)
