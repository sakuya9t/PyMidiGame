"""
GL smoke tests for the texture/overlay bridges (src/ui/gl_textures.py,
src/ui/gl_overlay.py).

These need a real OpenGL context, which the SDL 'dummy' video driver cannot
provide, so the whole module skips unless a context can be created. It therefore
runs on a real display (e.g. a dev machine) and auto-skips on CI / in the headless
discover suite. When it runs it proves the upload -> textured-quad -> blend path
works by reading the framebuffer back with glReadPixels.

Run it explicitly with:  python -m unittest tests.test_gl_textures
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame


def _try_gl_context(size=(64, 64)):
    try:
        pygame.display.quit()
        pygame.display.init()
        pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.OPENGL | pygame.HIDDEN)
        return True
    except Exception:
        return False


_GL_OK = _try_gl_context()


def _read_rgb(x, y):
    from OpenGL.GL import glReadPixels, GL_RGB, GL_UNSIGNED_BYTE
    raw = glReadPixels(x, y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)
    data = raw.tobytes() if hasattr(raw, 'tobytes') else bytes(raw)
    return data[0], data[1], data[2]


@unittest.skipUnless(_GL_OK, 'no OpenGL context available (headless/dummy driver)')
class TestGLTextureBridges(unittest.TestCase):

    SIZE = (64, 64)

    @classmethod
    def setUpClass(cls):
        pygame.display.quit()
        pygame.display.init()
        cls.screen = pygame.display.set_mode(
            cls.SIZE, pygame.DOUBLEBUF | pygame.OPENGL | pygame.HIDDEN)

    @classmethod
    def tearDownClass(cls):
        pygame.display.quit()

    def test_atlas_texture_loads_and_binds(self):
        from src.ui.gl_textures import AtlasTexture
        atlas = AtlasTexture()
        self.assertTrue(atlas.available)
        atlas.bind()  # uploads on first use; must not raise
        self.assertIsNotNone(atlas.uv('blue', 'note'))

    def test_atlas_missing_file_is_unavailable(self):
        from src.ui.gl_textures import AtlasTexture
        atlas = AtlasTexture(path='does-not-exist.png')
        self.assertFalse(atlas.available)
        atlas.bind()  # no-op, must not raise

    def test_surface_texture_update_and_bind(self):
        from src.ui.gl_textures import SurfaceTexture
        surf = pygame.Surface(self.SIZE, pygame.SRCALPHA)
        surf.fill((10, 20, 30, 255))
        tex = SurfaceTexture()
        tex.update(surf)
        self.assertEqual(tex.size, self.SIZE)
        tex.bind()  # must not raise

    def test_presenter_draws_surface_to_framebuffer(self):
        from OpenGL.GL import glClear, glClearColor, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT
        from src.ui.gl_overlay import SurfacePresenter

        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        surf = pygame.Surface(self.SIZE, pygame.SRCALPHA)
        surf.fill((220, 30, 40, 255))  # opaque red
        presenter = SurfacePresenter(self.SIZE)
        presenter.present(surf)

        r, g, b = _read_rgb(self.SIZE[0] // 2, self.SIZE[1] // 2)
        self.assertGreater(r, 180)
        self.assertLess(g, 90)
        self.assertLess(b, 90)


if __name__ == '__main__':
    unittest.main()
