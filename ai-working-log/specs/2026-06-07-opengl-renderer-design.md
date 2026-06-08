# Phase 3.3 — OpenGL Perspective Renderer (texture-first)

**Date:** 2026-06-07
**Status:** Design approved (proceed autonomously)
**Supersedes:** the 2D lane renderer in `src/ui/renderer.py` as the in-game renderer
**Related:** DESIGN.md §13 (In-Game Renderer), §16 (Visual Effects)

---

## 1. Goal

Replace the pygame 2D lane renderer with an **OpenGL vanishing-point
perspective** playfield (the DJmax look: notes appear small at a far vanishing
point and grow toward a hit bar at the bottom). The renderer must keep the same
decoupled inputs as today (`Chart` + `current_ms()` + `ScoringEngine` + engine
state) and must **not** reach into the legacy `Store`.

**Primary design constraint (per user):** texture rendering is *first-class*. The
existing neon texture atlas must drive the 3D scene through real GL textures, and
the material layer must be structured so richer visual effects (glow/additive
passes, animated UVs, bloom, particle effects) can be added later without
rework. "Perfect texturing now, fancy effects later."

## 2. Key decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Replace** the 2D renderer with GL (not an alternative backend) | User choice; matches DESIGN §13; smaller surface area |
| D2 | **One persistent OpenGL window**; menu/HUD/results are 2D surfaces presented as fullscreen textured quads | The `App` window is shared across screens; switching SDL display mode mid-run is flaky |
| D3 | **Immediate-mode GL** (compatibility profile: `glBegin/glEnd`, `gluPerspective`) | Minimal code, ports from `ui/graph`, fine for hundreds of quads; revisit only if note counts explode (YAGNI) |
| D4 | **Atlas uploaded once as a single GL texture; sub-rects → UV ranges** | First-class texturing; one bind per scene; future effects extend UVs/blends, not the upload path |
| D5 | Single shared **`ATLAS_RECTS`/UV table** used by both the GL scene and the 2D HUD `NeonMaterialKit` | One source of truth for the atlas; HUD keeps full atlas fidelity |
| D6 | Retire the broken `glDrawPixels` text path | Replaced by the surface→texture overlay |

## 3. Architecture overview

```
pygame.display.set_mode(SIZE, DOUBLEBUF | OPENGL)   # one GL context, whole app
        │
        ├─ MENU screen
        │     SongMenu.render(offscreen Surface)  ──► SurfacePresenter ──► fullscreen quad
        │
        └─ PLAYING / RESULTS screen
              3D pass (perspective, atlas-textured):
                  board quad → lane planes → hit bar → note boxes → press effects
              2D overlay pass:
                  HUD (score/combo/accuracy/DEMO) + countdown + results
                  drawn to an offscreen Surface (reusing NeonMaterialKit)
                  ──► SurfacePresenter ──► fullscreen quad ON TOP of the 3D scene
```

Two reusable bridges sit between pygame surfaces and GL:

- **`AtlasTexture`** — the neon atlas as a static GL texture + a `uv(family, name)`
  lookup. The 3D scene samples it.
- **`SurfacePresenter`** — uploads an arbitrary `pygame.Surface` (the menu, the
  HUD overlay) to a GL texture and draws it as a screen-space (ortho) quad with
  alpha blending. Used by both the menu and the gameplay HUD.

## 4. Texture & material system (centerpiece)

### 4.1 Shared atlas table — `src/ui/atlas.py`
Move the `_ATLAS_RECTS` dict (currently private to `NeonMaterialKit`) into a
shared module:

```python
ATLAS_SIZE = (1254, 1254)
ATLAS_RECTS = { 'blue': {...}, 'white': {...}, 'red': {...} }   # name -> (x, y, w, h)

def uv(family: str, name: str) -> tuple[float, float, float, float] | None:
    """Return (u0, v0, u1, v1) in [0,1], or None if absent.
    v is flipped to GL's bottom-left origin."""
```

`NeonMaterialKit` imports `ATLAS_RECTS` from here (behavior unchanged — same
rects, same 2D blits). The GL `AtlasTexture` imports `uv()`.

### 4.2 GL atlas texture — `src/ui/gl_textures.py`
```python
class AtlasTexture:
    def __init__(self, path=DEFAULT_ATLAS): ...     # lazy: GL upload on first bind()
    def bind(self) -> None: ...                      # glBindTexture(GL_TEXTURE_2D, id)
    def uv(self, family, name) -> UV | None: ...     # delegates to atlas.uv
    @property
    def available(self) -> bool: ...                 # False if atlas/GL missing -> flat-color fallback

class SurfaceTexture:
    """Wraps a dynamic pygame.Surface as a GL texture; re-upload on update()."""
    def update(self, surface: pygame.Surface) -> None: ...   # glTexImage2D from pygame bytes
    def bind(self) -> None: ...
```

Upload path: `pygame.image.tostring(surface, "RGBA", flipped=True)` →
`glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)`,
linear filtering, clamp-to-edge.

### 4.3 Material primitive
A single low-level helper renders every textured surface in the 3D scene:

```python
def textured_quad(verts: Sequence[Vec3], uv: UV, *, tint=(1,1,1,1),
                  blend='alpha') -> None
```

- `verts`: 4 world-space corners (CCW), `uv`: atlas region, `tint`: RGBA color
  multiply, `blend`: `'alpha'` (default) or `'add'` (glow).
- The atlas already carries per-family cells (blue/white/red) for
  lane/note/hold/key/spark, so the **family** is selected by UV (mirroring
  `NeonMaterialKit._family(color)`); `tint` then conveys per-note **state** —
  near-white for normal, green for `hit`, dim red for `missed` — matching how the
  2D renderer recolors notes today.
- Falls back to a flat tinted quad (no `glEnable(GL_TEXTURE_2D)`) when
  `AtlasTexture.available` is False — so the game still renders with no atlas.

**Why this is the extensibility seam:** future effects are new callers of
`textured_quad` (additive glow quads behind notes, UV-scrolling lane animation,
hit-spark billboards) or new blend modes — not changes to geometry or upload
code. A later `effects.py` (DESIGN §16) layers on top of this primitive.

## 5. Module breakdown

| Module | Responsibility | Tested headless? |
|--------|----------------|------------------|
| `src/ui/atlas.py` | Atlas rect table + `uv()` math | ✅ pure |
| `src/ui/geometry.py` | World-space math: `note_z`, `lane_world_x`, `note_box_world`, **hold-length clamp** | ✅ pure |
| `src/ui/gl_textures.py` | `AtlasTexture`, `SurfaceTexture` | ⛔ needs GL context (smoke, skip-guarded) |
| `src/ui/gl_overlay.py` | `SurfacePresenter` (ortho fullscreen textured quad) | ⛔ GL smoke |
| `src/ui/hud.py` | 2D HUD/countdown/results onto an offscreen Surface (extracted from today's renderer; uses `NeonMaterialKit`) | ✅ surface blit under SDL dummy |
| `src/ui/renderer.py` | GL `Renderer`: camera + 3D passes + HUD presentation | ⛔ GL smoke |

`src/game/*` and `src/ui/menu.py` are unchanged.

### 5.1 Renderer interface (changed)
The `target` surface argument is **removed** — GL draws to the bound context:

```python
class Renderer:
    def __init__(self, size: tuple[int, int]) -> None: ...
    def render(self, chart: Chart, current_ms: float, scoring: ScoringEngine, *,
               state: GameState, countdown: int = 0, is_demo: bool = False) -> None: ...
```

Internal passes: `_setup_camera()`, `_draw_board()`, `_draw_lanes(lane_count)`,
`_draw_hit_bar()`, `_draw_notes(chart, current_ms)`, `_draw_press_effects(...)`,
then `_present_hud(...)` (build HUD surface via `hud.py`, upload, draw quad).

## 6. Coordinate & camera model

Port the legacy `game_board_*` constants, parameterized by `lane_count`:

- **Board:** fixed quad in world space; `BOARD_LEFT/RIGHT/NEAR/FAR` on the XZ
  plane (y≈0). Lanes span `[BOARD_LEFT, BOARD_RIGHT]`.
- **Camera:** `gluPerspective(45, w/h, 0.1, 50)`; translate back, then
  `glRotatef(~30°, 1,0,0)` to look down the track (legacy values as the start
  point, tuned during verification).
- **Note Z:** `z = (note.time_ms − current_ms) * UNITS_PER_MS`. Future → far Z;
  hit time → near Z (≈ hit bar). Perspective maps Z→screen-Y for free.
- **Lane X:** `lane_world_x(lane, lane_count, left, right)` — linear across the
  board (generalizes legacy's hardcoded 32-key / `C3`).
- **Hold length:** clamp a note's Z-extent to the visible board (fixes the legacy
  `draw_note` "longer than board" FIXME) — pure, unit-tested.
- **Note color:** reuse the 2D renderer's lane-color rule (odd center lane = red;
  alternating blue/white) as the `textured_quad` tint, so MIDI/PC layouts read
  the same as today.

## 7. `app.py` wiring

- `App.run()` and the legacy `run()` open `set_mode(SIZE, DOUBLEBUF | OPENGL)`.
- `App` owns a `SurfacePresenter` and a reusable offscreen `pygame.Surface`.
  - **MENU:** `menu.render(offscreen)` → `presenter.present(offscreen)`.
  - **PLAYING/RESULTS:** `renderer.render(chart, ...)` (no surface arg).
- `SongMenu` is untouched (still renders to a Surface) → its 22 tests stay green.
- Each frame: `glClear(...)` → draw → `pygame.display.flip()` (double-buffered).

## 8. Testing strategy

The project's headless TDD can't cover real GL draws (the dummy SDL driver has no
GL). We preserve discipline by **maximizing the pure, testable core** and
**guarding** the GL parts:

- **Pure unit tests (headless, keep the suite green):**
  - `tests/test_atlas.py` — `uv()` ranges in [0,1], v-flip, missing-name → None.
  - `tests/test_geometry.py` — `note_z` sign/scale, `lane_world_x` anchors &
    even spacing, `note_box_world` corners, hold-length clamp at both bounds.
  - `tests/test_hud.py` — HUD/countdown/results draw onto a Surface under
    `SDL_VIDEODRIVER=dummy` without error (reuses today's overlay coverage).
- **GL smoke test** — `tests/test_gl_renderer.py`: try to create a real OPENGL
  context; `@unittest.skipUnless` it succeeds. When it runs (e.g. your Windows
  display) it executes one full `Renderer.render(...)` frame + a
  `SurfacePresenter.present(...)` without GL error. Auto-skips on CI/dummy.
- **Game-loop coverage moves to a renderer-free harness:** the existing
  end-to-end "demo run finishes at 1,000,000 / S" assurance is retained by
  driving engine+scoring+demo+clock *without* the renderer (it already passes in
  `test_demo_player.py`). We therefore **drop** `test_renderer.py`'s
  `TestHeadlessPlayableLoop` (it depended on the 2D renderer's surface draw); the
  pure-math and game-loop guarantees survive.

**Manual verification (autonomous):** launch `python mania.py songs/twinkle` (or
a fixture) on the real display, confirm the perspective playfield renders, notes
fall to the hit bar, HUD overlays correctly, countdown + results show; capture a
screenshot. Run the full `unittest` suite and report counts.

## 9. Milestones (one commit each)

1. **Atlas + geometry foundation** — `atlas.py` (+ `NeonMaterialKit` imports it),
   `geometry.py`, their pure tests. Suite green.
2. **GL bridges** — `gl_textures.py` (`AtlasTexture`, `SurfaceTexture`),
   `gl_overlay.py` (`SurfacePresenter`) + GL smoke (skip-guarded).
3. **GL renderer** — rewrite `renderer.py` (camera + textured 3D passes +
   `hud.py` extraction + HUD presentation); update/replace renderer tests.
4. **Wire-up & verify** — `app.py`/`mania.py` to OPENGL display; menu via
   presenter; run on the real display + screenshot; update `TRACKING.md`.

## 10. Out of scope (future, but enabled by this design)

- Bloom/glow post-processing, animated UV scrolling, particle hit effects
  (DESIGN §16 `effects.py`) — all layer onto `textured_quad`/`blend='add'`.
- Beveled 3D note *meshes* (legacy `draw_note` had a chamfered box); v1 uses
  textured flat quads facing the camera for clarity — 3D meshing is a later
  visual upgrade.
- Modern shader/VBO pipeline (only if note counts demand it).

## 11. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| GL context unavailable in some environments | `AtlasTexture.available` / flat-color fallback; `run()` already degrades audio to silent — add a clear error if GL `set_mode` fails |
| Per-frame HUD texture upload cost | One `glTexImage2D` of a 960×720 RGBA surface/frame is cheap at 60 FPS; re-upload only the HUD (small), reuse atlas texture |
| Lost headless render smoke | Pure-math + game-loop coverage retained; GL smoke runs on dev display |
| Immediate mode deprecation | Compatibility profile is fine; isolated behind `textured_quad` for a future swap |
