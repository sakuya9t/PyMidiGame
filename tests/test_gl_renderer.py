"""
GL smoke tests for the perspective renderer (src/ui/renderer.py).

Needs a real OpenGL context, so the module skips unless one can be created (runs
on a real display, auto-skips under the SDL dummy driver / on CI). When it runs
it drives a full scene and reads the framebuffer back to prove the playfield
actually rasterizes pixels.

Run explicitly with:  python -m unittest tests.test_gl_renderer
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame


def _try_gl_context(size=(320, 240)):
    try:
        pygame.display.quit()
        pygame.display.init()
        pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.OPENGL | pygame.HIDDEN)
        return True
    except Exception:
        return False


_GL_OK = _try_gl_context()

from src.game.chart import Note, Chart
from src.midi.classifier import KeyboardClass

_KB = KeyboardClass(name='25key', key_count=25, midi_low=48, midi_high=72, lane_count=25)


def _framebuffer_max(width, height):
    from OpenGL.GL import glReadPixels, GL_RGB, GL_UNSIGNED_BYTE
    raw = glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE)
    data = raw.tobytes() if hasattr(raw, 'tobytes') else bytes(raw)
    return max(data)


def _chart(lane_count=8):
    notes = [Note(lane=i % lane_count, midi_note=48 + i, time_ms=300.0 + i * 200.0,
                  duration_ms=(150.0 if i % 3 == 0 else 0.0)) for i in range(12)]
    return Chart(notes=notes, kb_class=_KB, mode='pc', lane_count=lane_count,
                 total_duration_ms=notes[-1].time_ms)


@unittest.skipUnless(_GL_OK, 'no OpenGL context available (headless/dummy driver)')
class TestGLRenderer(unittest.TestCase):

    SIZE = (320, 240)

    @classmethod
    def setUpClass(cls):
        pygame.display.quit()
        pygame.display.init()
        cls.screen = pygame.display.set_mode(
            cls.SIZE, pygame.DOUBLEBUF | pygame.OPENGL | pygame.HIDDEN)

    @classmethod
    def tearDownClass(cls):
        pygame.display.quit()

    def test_scene_rasterizes_pixels(self):
        from src.ui.renderer import Renderer
        renderer = Renderer(self.SIZE)
        renderer.render(_chart(), current_ms=400.0)  # notes around the hit bar
        # The neon scene (hit bar, lanes, notes) is far brighter than the very
        # dark background, so some channel must be lit.
        self.assertGreater(_framebuffer_max(*self.SIZE), 120)

    def test_handles_countdown_and_finished_positions(self):
        from src.ui.renderer import Renderer
        renderer = Renderer(self.SIZE)
        renderer.render(_chart(), current_ms=-2000.0)  # pre-roll (countdown)
        renderer.render(_chart(), current_ms=999999.0)  # past the end
        # Just proving these scroll positions render without GL error.

    def test_flat_fallback_without_atlas(self):
        from src.ui.renderer import Renderer
        from src.ui.gl_textures import AtlasTexture
        renderer = Renderer(self.SIZE)
        renderer._atlas = AtlasTexture(path='does-not-exist.png')
        self.assertFalse(renderer._atlas.available)
        renderer.render(_chart(), current_ms=400.0)  # flat-color path, no raise

    def test_nine_lane_pc_layout(self):
        from src.ui.renderer import Renderer
        renderer = Renderer(self.SIZE)
        renderer.render(_chart(lane_count=9), current_ms=400.0)


if __name__ == '__main__':
    unittest.main()
