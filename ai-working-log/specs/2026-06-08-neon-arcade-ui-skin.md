# Phase 5.x — Neon Arcade UI Skin

**Date:** 2026-06-08  
**Status:** Ready for Claude implementation  
**Related:** `resources/ui/neon_arcade_skin_resources.json`, `resources/ui/neon_texture_atlas.png`, `src/ui/atlas.py`, `src/ui/materials.py`, `src/ui/hud.py`, `src/ui/renderer.py`

---

## 1. Goal

Upgrade the current usable neon HUD into a richer arcade-style UI using the
existing atlas as the primary visual source. The target is the kind of score,
combo, song info, gauge, lane, and hit-effect treatment shown in the user's
reference: beveled neon frames, textured panel interiors, glowing score digits,
red combo emphasis, lane impact sparks, and small decorative accents.

The implementation should be **atlas-first**, not primitive-first. Pygame drawing
is still allowed for dynamic text, runtime-generated overlays, masks, and fallback
paths, but the visible HUD shells and major decorative elements should come from
`resources/ui/neon_texture_atlas.png`.

---

## 2. Resource Gap Analysis

The primary atlas image is not the main blocker. It already contains many assets
that look close to the reference, but most are not yet registered in
`src/ui/atlas.py`.

### 2.1 Already Registered And Usable

These are already named in `src/ui/atlas.py`:

- `blue|white|red/lane`
- `blue|white|red/note`
- `blue|white|red/hold`
- `blue|white|red/key`
- `blue|white|red/panel`
- `blue/gauge_empty`
- `blue/gauge_filled`
- `blue|white|red/spark`
- `blue/hit`

### 2.2 Present In The Atlas But Missing From The Code Registry

Register these before attempting the new skin:

- Dedicated HUD frames:
  - `blue/score_panel`
  - `red/combo_panel`
  - `blue/song_info_panel`
  - `blue/gauge_panel`
  - `blue/small_stat_box`
  - `blue/generic_wide_panel`
- Gauge polish:
  - `blue/gauge_overlay_glow`
  - `blue/meter_piece_full`
- Decorative density:
  - `blue/decor_corner`
  - `blue/decor_line`
  - `blue/arrows`
  - `blue/screw_decal`
- FX:
  - `blue|white|red/impact_spark`
  - `blue|white|red/glint_tiny`
- Results polish:
  - `rank/rank_c`
  - `rank/rank_b`
  - `rank/rank_a`
  - `rank/rank_s`
  - `rank/rank_s_plus`

The supplemental resource catalog is:

```text
resources/ui/neon_arcade_skin_resources.json
```

That file identifies which assets are present-but-unregistered, which should be
generated at runtime, and which are optional external assets.

Measured atlas rects are included in that JSON as `rect: [x, y, w, h]`. These
are the same coordinates, listed here for direct implementation:

| Family | Name | Rect `(x, y, w, h)` | Notes |
|--------|------|----------------------|-------|
| `blue` | `score_panel` | `(740, 67, 484, 101)` | Alias of existing `blue/panel`; existing careful measurement |
| `red` | `combo_panel` | `(739, 214, 483, 90)` | Alias of existing `red/panel`; existing careful measurement |
| `blue` | `song_info_panel` | `(739, 340, 243, 104)` | Full song info frame, including equalizer strip |
| `blue` | `gauge_panel` | `(1009, 338, 209, 84)` | Full oval gauge shell |
| `blue` | `small_stat_box` | `(744, 481, 123, 73)` | Small stat frame only, excluding label text |
| `blue` | `generic_wide_panel` | `(894, 476, 342, 86)` | Full generic wide frame and accents |
| `blue` | `gauge_overlay_glow` | `(740, 754, 490, 30)` | Additive bar glow |
| `blue` | `meter_piece_full` | `(743, 820, 60, 25)` | First segmented meter piece |
| `blue` | `decor_corner` | `(18, 932, 37, 37)` | First decorative corner part |
| `blue` | `decor_line` | `(18, 992, 377, 10)` | Long horizontal accent line |
| `blue` | `impact_spark` | `(560, 1036, 110, 102)` | Alias of existing `blue/spark` |
| `white` | `impact_spark` | `(673, 1036, 110, 102)` | Alias of existing `white/spark` |
| `red` | `impact_spark` | `(787, 1036, 110, 102)` | Alias of existing `red/spark` |
| `blue` | `glint_tiny` | `(706, 1045, 120, 80)` | Blue-side tiny particles group |
| `white` | `glint_tiny` | `(840, 1045, 165, 80)` | Neutral tiny particles group |
| `red` | `glint_tiny` | `(1035, 1045, 185, 80)` | Red-side tiny particles group |
| `blue` | `life_icon` | `(118, 1184, 60, 50)` | Heart only, label excluded |
| `blue` | `multiplier_chip` | `(558, 1186, 66, 50)` | `x8` chip |
| `blue` | `arrows` | `(682, 1195, 90, 31)` | Arrow strip |
| `blue` | `screw_decal` | `(1110, 1198, 20, 20)` | First screw decal |
| `rank` | `rank_c` | `(201, 1177, 57, 60)` | Results badge |
| `rank` | `rank_b` | `(266, 1177, 57, 60)` | Results badge |
| `rank` | `rank_a` | `(331, 1177, 57, 60)` | Results badge |
| `rank` | `rank_s` | `(394, 1177, 57, 60)` | Results badge |
| `rank` | `rank_s_plus` | `(461, 1177, 58, 60)` | Results badge |

Nine-slice source borders have also been measured. Use the order
`(left, top, right, bottom)`:

| Family | Name | Nine-Slice Border | Measurement Rationale |
|--------|------|-------------------|-----------------------|
| `blue` | `score_panel` | `(42, 24, 50, 26)` | Preserves left layered corner, right end cap, top bevels, bottom glow/accent band |
| `red` | `combo_panel` | `(42, 22, 44, 26)` | Preserves left layered corner, right end cap, bottom glow/accent band |
| `blue` | `song_info_panel` | `(92, 18, 30, 34)` | Preserves the built-in jacket aperture and bottom equalizer strip |
| `blue` | `gauge_panel` | `(46, 24, 46, 24)` | Preserves the oval end caps and outer rings |
| `blue` | `small_stat_box` | `(34, 22, 34, 22)` | Preserves all four chamfered corner stacks |
| `blue` | `generic_wide_panel` | `(44, 22, 44, 24)` | Preserves left/right bevel stacks and bottom accent band |

The same data is mirrored in
`resources/ui/neon_arcade_skin_resources.json` as `nine_slice_border` and
`nine_slice_min_size`.

### 2.3 Not In The Current Atlas

These are not in `neon_texture_atlas.png`, so they were generated as separate
project resources for the first skin pass:

- `resources/ui/neon_arcade_stage_background.png` — 1672x941 optional gameplay
  backdrop with a dark center for the note highway.
- `resources/ui/neon_arcade_jacket_placeholder.png` — 1254x1254 fallback song
  jacket art.
- `resources/ui/neon_arcade_panel_texture_tile.png` — 1254x1254 low-contrast
  sci-fi panel interior texture.

Still use runtime-generated surfaces for scanlines, text glow, and any dynamic
vignette. Use pygame fonts for score/combo text with glow passes. Do not use
generated bitmap text for score digits or "FULL COMBO!" in this pass; model-made
text is too unreliable for dynamic UI.

---

## 3. Architecture

Add one new high-level module and extend the current material layer.

```text
src/ui/atlas.py
  Register new named atlas rects.

src/ui/materials.py
  Low-level atlas blitting, nine-slice scaling, additive glow, text glow,
  runtime-generated noise/scanline helpers.

src/ui/skin.py
  New high-level NeonArcadeSkin API:
    draw_song_panel()
    draw_gauge_panel()
    draw_score_panel()
    draw_combo_panel()
    draw_small_stat_box()
    draw_hit_spark()

src/ui/hud.py
  Layout only. Delegate visual chrome to NeonArcadeSkin.

src/ui/renderer.py
  Add atlas lane overlay and improved hit-line/note glow polish.
```

Keep `src/ui/atlas.py` as the numeric source of truth. Do not scatter atlas rects
through `materials.py`, `skin.py`, or `hud.py`.

---

## 4. Implementation Plan

### Step 1 — Register The Missing Atlas Regions

Add the high-value regions listed in section 2.2 to `ATLAS_RECTS`.

Do not re-measure these by hand unless a visual verification catches a problem.
Use the measured coordinate table above and the `rect` fields in
`resources/ui/neon_arcade_skin_resources.json`.

Also use the measured `nine_slice_border` values from the table above. Do not
guess border thickness during implementation; the implementation's job is to
consume the measured data and verify visually.

Minimum first pass:

- `blue/score_panel`
- `red/combo_panel`
- `blue/song_info_panel`
- `blue/gauge_panel`
- `blue/small_stat_box`
- `blue/generic_wide_panel`
- `blue/gauge_overlay_glow`
- `blue|white|red/impact_spark`
- `blue|white|red/glint_tiny`

Update `tests/test_atlas.py` so it verifies:

- New names exist.
- Their UVs remain inside `[0, 1]`.
- Unknown names still return `None`.

### Step 2 — Add Nine-Slice Panel Rendering

Extend `NeonMaterialKit` with a helper similar to:

```python
def draw_nine_slice(
    self,
    surface: pygame.Surface,
    family: str,
    name: str,
    rect: pygame.Rect,
    border: tuple[int, int, int, int],  # left, top, right, bottom
    *,
    alpha: int = 255,
) -> bool:
    ...
```

Behavior:

- Preserve four corners without distortion.
- Stretch top/bottom edges horizontally.
- Stretch left/right edges vertically.
- Fill the center with a dark translucent color and optional runtime noise tile.
- Return `False` if the atlas asset is unavailable, allowing fallback drawing.
- Clamp or fallback if the target rect is smaller than `left + right` or
  `top + bottom`; never create negative center sizes.

Do not replace every old panel immediately. First use nine-slice for score,
combo, song info, gauge, and small stat panels.

### Step 3 — Add Glow And Runtime Overlay Helpers

Add helpers to `NeonMaterialKit` or a small internal helper section:

- `draw_glow_text(surface, font, text, pos_or_rect, color, glow_color, align=...)`
- `draw_additive_asset(surface, family, name, rect, alpha=...)`
- `make_noise_tile(size, seed=...)`
- `make_scanline_tile(size=...)`
- `load_optional_ui_image(path) -> pygame.Surface | None`

Rules:

- Use deterministic generation. No random per-frame flicker.
- Use `pygame.BLEND_RGBA_ADD` for glow/spark overlays where possible.
- Keep text crisp by drawing the foreground text last.
- Prefer `neon_arcade_panel_texture_tile.png` for panel interiors, with a
  deterministic noise fallback if the file is unavailable.

### Step 4 — Create `src/ui/skin.py`

Implement:

```python
class NeonArcadeSkin:
    def __init__(self, materials: NeonMaterialKit | None = None) -> None: ...

    def draw_song_panel(self, target, rect, *, title, artist=None, bpm=None, jacket=None): ...
    def draw_gauge_panel(self, target, rect, *, value, label='GAUGE'): ...
    def draw_score_panel(self, target, rect, *, score): ...
    def draw_combo_panel(self, target, rect, *, combo, full_combo=False): ...
    def draw_small_stat_box(self, target, rect, *, label, value, color='blue'): ...
    def draw_hit_spark(self, target, center, *, family='blue', intensity=1.0): ...
```

The skin owns visual decisions: panel asset choice, glow colors, text sizes,
noise overlays, tiny glints, and decorative strips. `HudOverlay` should not know
how a panel is drawn.

The skin should load `resources/ui/neon_arcade_jacket_placeholder.png` and
`resources/ui/neon_arcade_panel_texture_tile.png` if available, but it must keep
working without them.

### Step 5 — Simplify `HudOverlay`

Change `src/ui/hud.py` so it computes layout and delegates visual rendering to
`NeonArcadeSkin`.

Minimum layout at the current shipping resolution, **1366x768**:

| Panel | Rect `(x, y, w, h)` | Notes |
|-------|----------------------|-------|
| song panel | `(28, 24, 404, 154)` | Left column top; large enough for jacket placeholder + title lines |
| gauge panel | `(28, 194, 356, 88)` | Left column below song panel |
| small stat box | `(28, 320, 174, 96)` | HI-SPEED/mode/demo status; do not extend below `y=430` in first pass |
| score panel | `(940, 24, 398, 130)` | Right aligned with 28px visual margin |
| combo panel | `(998, 176, 340, 126)` | Right aligned, narrower than score for hierarchy |

Reserved transparent inspection area:

```text
Rect(448, 70, 470, 560)
```

No normal gameplay HUD panel should place opaque pixels inside that central area.
The center points `(683, 384)` and `(683, 520)` should remain transparent in the
normal gameplay HUD, matching the existing `tests/test_hud.py` intent.

For other resolutions, scale from the 1366x768 base using:

```python
scale = min(width / 1366, height / 768)
```

Then anchor left-column panels to the left margin and right-column panels to the
right margin. The first implementation may hardcode 1366x768 if tests and
`src/app.py::SIZE` are already fixed there, but keep the layout data isolated so
responsive scaling can be added without rewriting the skin.

Do not add blocking dependencies on song metadata in the first pass. If `HudOverlay`
does not receive title/artist/BPM yet, use current stable labels and leave app
wiring as a follow-up.

### Step 6 — Polish The 3D Renderer With Existing Atlas Assets

In `src/ui/renderer.py`, update lane rendering from pure color only to a two-pass
style:

1. Draw the current flat lane color for clarity.
2. Draw the corresponding `family/lane` atlas texture at low alpha over it.

This keeps 49-key MIDI mode readable while adding atlas texture.

Also consider:

- Add a second low-alpha hit-line glow pass using `blue/hit`.
- Use `impact_spark` later through the HUD/effects path when hit events are
  available. Do not fake hit-event state in `Renderer` unless the game engine
  already exposes it cleanly.
- Treat `resources/ui/neon_arcade_stage_background.png` as optional. If it is
  integrated now, draw it before the board/lanes and preserve the dark readable
  playfield center. If that requires risky GL texture/layout work, leave it as a
  documented follow-up rather than blocking the HUD skin.

---

## 5. Expected Result

The first finished pass should look materially richer than the current HUD:

- Score and combo boxes use distinct atlas panel art, not generic drawn rects.
- Score text has blue-white glow and remains readable.
- Combo text has red-white glow and strong visual hierarchy.
- Gauge uses atlas bar art plus a glow overlay.
- Left HUD includes a song/info style panel with a jacket placeholder or compact
  title block.
- Panel interiors have subtle dark texture/noise rather than plain flat fill.
- The generated jacket placeholder is used when no song art is available.
- Small atlas decorative accents appear around HUD panels without cluttering the
  playfield.
- The center playfield remains unobstructed and transparent in the HUD overlay.
- Lanes show subtle atlas texture while keeping current MIDI/PC color logic.

It does **not** need to perfectly recreate the reference screenshot in one pass.
The target is a shippable arcade-styled skin foundation.

---

## 6. Definition Of Done

Implementation is done when all of the following are true:

- `resources/ui/neon_arcade_skin_resources.json` is either loaded for validation
  or mirrored by equivalent code/tests; its classifications remain accurate.
- `src/ui/atlas.py` registers the minimum first-pass assets from section 4 step 1.
- `NeonMaterialKit` supports nine-slice atlas panel rendering.
- `NeonArcadeSkin` exists and owns the score/combo/song/gauge/small-stat visual
  rendering.
- `HudOverlay` delegates panel visuals to `NeonArcadeSkin` and remains mostly
  layout/state code.
- Score, combo, gauge, and song/info panels are visibly atlas-backed.
- Generated supplemental images are present and documented:
  - `resources/ui/neon_arcade_stage_background.png`
  - `resources/ui/neon_arcade_jacket_placeholder.png`
  - `resources/ui/neon_arcade_panel_texture_tile.png`
- Dynamic text uses glow rendering but remains crisp and readable.
- HUD rendering still starts from a transparent surface.
- The center of the HUD overlay remains transparent during gameplay.
- The GL renderer applies a subtle lane atlas overlay without harming lane
  readability.
- Fallback behavior still works if the atlas is missing: no crash, flat/procedural
  drawing is acceptable.
- No new mandatory dependency is added.
- Relevant tests pass.

---

## 7. Verification

Run focused tests first:

```powershell
python -m unittest tests.test_atlas tests.test_hud tests.test_gl_textures
```

Then run the full suite:

```powershell
python -m unittest
```

Manual verification on a real display:

```powershell
python mania.py songs/twinkle
```

Check these visually:

- Score panel appears in the upper right with blue frame art and glow digits.
- Combo panel appears below score with red frame art and glow digits.
- Left song/gauge area uses atlas-framed panels.
- Gauge fill and glow update with accuracy.
- No HUD text overlaps panel borders at 1366x768.
- The central lane area remains visible and is not covered by opaque HUD pixels.
- Lanes have subtle texture but note readability is not worse than before.
- Countdown and results still render without crashing.

Recommended extra checks:

- Temporarily rename `resources/ui/neon_texture_atlas.png` and run the focused
  HUD tests to confirm fallback rendering does not crash. Restore the file
  immediately after the check.
- Take before/after screenshots at 1366x768. If responsive scaling is implemented,
  also capture one smaller smoke size.
- Inspect the HUD surface alpha at the screen center in `tests/test_hud.py`; it
  should remain `pygame.Color(0, 0, 0, 0)` for normal gameplay HUD.

---

## 8. Guardrails For Claude

- Prefer small, testable changes over a large visual rewrite.
- Do not hardcode atlas coordinates outside `src/ui/atlas.py`.
- Do not make the HUD depend on unavailable song cover art.
- Do not introduce shaders, bloom post-processing, or a new rendering backend in
  this pass.
- Do not remove existing fallback behavior.
- Avoid making 49-key MIDI lanes visually noisy; readability beats texture density.
- Keep the implementation deterministic so tests and screenshots are stable.
- If a desired visual cannot be done cleanly with current game state, leave a
  clear TODO in the spec/report rather than inventing hidden state.
