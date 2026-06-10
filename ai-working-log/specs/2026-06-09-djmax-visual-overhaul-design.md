# Phase 6 — DJMAX-Style Visual Experience Overhaul

**Date:** 2026-06-09
**Status:** Design — ready for review, then per-phase implementation
**Related:** `src/ui/renderer.py`, `src/ui/hud.py`, `src/ui/skin.py`, `src/ui/materials.py`,
`src/ui/menu.py`, `src/ui/results.py`, `src/app.py`, `src/game/scoring.py`,
`resources/ui/neon_arcade_stage_background.png`

---

## 1. Goal

The game is functionally complete but visually static. The target is a
**DJMAX-style audiovisual experience**: a playfield that reacts to every press,
judgment feedback that celebrates accuracy, a stage that breathes with the music,
and menus/results that move. "It draws the right thing" must become "it feels
alive every frame."

This is a **motion and feedback** overhaul, not another texture pass. Phase 5
gave us atlas-backed chrome; Phase 6 gives us **time**: easing, particles,
beams, popups, pulses, count-ups, and transitions — all deterministic and
testable.

### 1.1 Current-State Assessment (evidence)

From reading the code and the offscreen captures in `tmp/`:

| Area | Today | Why it reads as "just working" |
|---|---|---|
| Judgment feedback | `register_hit()` returns a `Judgment` that the engine **throws away**; only aggregate counts survive | The single most important rhythm-game feedback loop (PERFECT/GREAT/GOOD per hit) is invisible |
| Key press feedback | `KEYUP` is ignored; a press that hits nothing shows nothing | No keybeam — the player's own input is mute |
| Animation | Nothing eases or pulses; the only time-driven visuals are note scroll and a 260 ms spark fade | Score/combo snap to new values; countdown is a static number; FULL COMBO is static text |
| Stage | Flat `_BG` clear color; the board floats in a black void (see `tmp/strong_hit_fx_keyed_capture.png`); `neon_arcade_stage_background.png` exists but is unused (Phase 5 deferral) | ~60% of the screen is empty darkness |
| Beat awareness | None — visuals don't know the BPM | The screen ignores the music it's playing |
| Lane dividers / rails | `GL_LINES` (driver-dependent width, no texture, no motion) | Reads as wireframe, not a neon "gear" |
| Menu | Plain text rows on a flat fill, no skin panels, no motion | The first screen the player sees is the weakest |
| Results | Static numbers appear instantly | No reveal, no ceremony for an S rank |
| Transitions | Screens hard-cut | Every screen change is a jolt |

### 1.2 What We Take From DJMAX's Visual Language

DJMAX Respect V's look, decomposed into adoptable elements (ordered by impact):

1. **Keybeams** — a vertical light column flares up the lane on key press and
   fades on release. The single highest-impact effect: the game answers *every*
   input instantly, hit or not.
2. **Judgment popups** — "PERFECT / GREAT / GOOD / MISS" pops above the judge
   line with a scale-in + float-up + fade, color-coded per grade.
3. **Combo counter on the gear** — big animated digits above the playfield
   center that pulse on every hit, escalating presentation at milestones.
4. **Layered hit explosions** — shockwave ring + radial sparks + flash, scaled
   by grade (PERFECT bursts gold; GOOD barely glints).
5. **The gear frame** — bright side rails with flowing energy, a glowing judge
   line, a track that reads as a physical object, not floor stripes.
6. **A live stage** — animated backdrop (BGA substitute: parallax grid,
   drifting particles, beat-pulsed glow) so the void around the gear is alive.
7. **Motion-first UI** — eased menu navigation, screen transitions, results
   that count up and slam the rank badge in.

We explicitly do **not** adopt: video BGAs (out of scope v1), FEVER gameplay
mechanics (visual-only escalation instead), or licensed skin art.

---

## 2. Constraints & Capabilities

These bind every design decision below:

- **Fixed-function immediate-mode GL** (`glBegin/glEnd`, GLU camera). No
  shaders/FBOs until the optional final phase; all glow is **pre-baked sprites +
  additive blending** (`GL_SRC_ALPHA, GL_ONE`), which the renderer already uses
  for sparks.
- **Two composition layers**: the 3D GL scene, then one fullscreen pygame
  SRCALPHA surface (`SurfacePresenter`). Playfield-anchored FX belong in the GL
  layer (correct perspective, doesn't fight the HUD-transparency tests); panel
  animation belongs in the HUD layer.
- **Headless test discipline**: FX/animation *state* must be pure Python data,
  testable under the dummy driver. GL smoke tests run standalone
  (`python -m unittest tests.test_gl_renderer`); visuals are verified by
  offscreen capture (HIDDEN window + `glReadPixels`, per the established
  workflow).
- **Determinism**: no per-frame randomness. Particle trajectories seed from
  `(lane, note_time_ms)`; everything else is a pure function of `current_ms`.
- **HUD center stays transparent** (`tests/test_hud.py` inspection band
  `Rect(448, 70, 470, 560)`): all new center-screen visuals (popups, combo,
  keybeams) live in the **GL layer**, so the HUD contract is untouched.
- **Python perf budget**: 16.6 ms/frame at 60 FPS. Immediate mode costs ~1 µs
  per vertex call in Python; budget ≈ 2,000 quads/frame. Mitigations: batch
  quads per texture bind (one `glBegin` for all notes), cap live particles
  (§8), and never allocate per-frame.
- **Graceful degradation**: every effect must no-op cleanly if its baked
  texture failed to build; flat-color fallbacks stay intact.

---

## 3. Architecture

Four new modules carry the overhaul; existing modules grow thin hooks.

```text
src/ui/anim.py          NEW  Pure math: easing, Pulse, RollingValue, Timeline,
                             BeatClock. Zero pygame/GL imports. Fully unit-tested.

src/ui/effects.py       NEW  FxManager: pure-data FX state machine.
                             Ingests events (judgment, press/release, combo),
                             update(now_ms) advances, emits draw-list dataclasses.
                             Zero GL imports — headless-testable.

src/ui/fx_draw.py       NEW  GL draw pass for FxManager draw lists + baked
                             sprite/text textures (the only new GL-touching file).

src/ui/skin_pack.py     NEW  Data-driven skin packages: skin.json manifest ->
                             regions, nine-slice, palette, images, FX overrides.
                             Discovery + selection. No GL imports. (§4)

src/ui/atlas.py         MOD  Becomes a facade over the active SkinPack; the
                             hardcoded numeric tables move into the default
                             skin's manifest. Public API (uv, nine_slice)
                             unchanged, so no consumer changes.

src/game/scoring.py     MOD  recent_judgments(now): grade-carrying event stream
                             (extends the recent_hits pattern; scoring already
                             owns hit state — this stays the single source).

src/ui/renderer.py      MOD  Stage background, gear rails, batched notes,
                             FX passes, combo billboard. Gains a `now_ms`-driven
                             animated layer order (§3.3).

src/ui/hud.py, skin.py  MOD  render(..., now_ms): combo pop, score roll,
                             gauge sweep, countdown animation.

src/ui/menu.py          MOD  Skin-panel restyle + eased list scrolling +
                             animated backdrop.

src/ui/results.py       MOD  Timeline-staged reveal (count-ups, rank slam).

src/app.py              MOD  Routes lane press/release to FxManager; screen
                             crossfade transitions; passes now_ms to 2D layers.
```

### 3.1 `src/ui/anim.py` — the animation vocabulary

```python
def ease_out_cubic(t: float) -> float          # UI pops, popup scale-in
def ease_out_back(t: float) -> float           # rank slam overshoot
def ease_in_quad(t: float) -> float            # fade-outs
def clamp01(t: float) -> float

class Envelope:
    """A multi-stage keyframe curve: a sequence of (duration_ms, ease_fn,
    from_value, to_value) segments evaluated at an age. The backbone of every
    FX animation — e.g. alpha 0->1 over 40 ms (flare-in), hold 1.0 for 60 ms
    (glow), 1->0 over 160 ms (fade-out). value(age_ms) is pure; total_ms tells
    owners when the FX is dead. Segments may hold (from == to)."""

class Pulse:
    """A retriggerable decay envelope: trigger(now) -> value(now) in [0,1]
    decaying over duration_ms. Drives combo pop, beat flash, milestone flare."""

class RollingValue:
    """Displayed number chasing a target: set(value, now); value(now) closes
    the gap exponentially (half-life ~80 ms). Drives score roll-up and
    smooth gauge fill."""

class Timeline:
    """Named keyframe segments with per-segment easing; t(name, now) in [0,1].
    Drives the staged results reveal and screen transitions."""

class BeatClock:
    """bpm + anchor_ms -> beat_phase(now) in [0,1) and beat_index(now).
    Visual-only; never touches scoring."""
```

BPM source order: `meta.json` bpm → median inter-onset gap of the chart
(folded into 60–180 range) → 120. Good enough for pulsing; judgment timing is
untouched.

### 3.2 `src/ui/effects.py` — FX state, pure data

```python
@dataclass(frozen=True)
class JudgmentPop:    # grade, lane, born_ms  -> popup above the judge line
@dataclass(frozen=True)
class Shockwave:      # lane, grade, born_ms  -> expanding ring at hit point
@dataclass(frozen=True)
class BurstParticle:  # seeded (lane, note_time) -> 6–10 flying glints per hit
@dataclass
class Keybeam:        # lane, pressed_ms, released_ms|None -> column flare
@dataclass
class PressMarker:    # lane, pressed_ms, released_ms|None -> the DJMAX-style
                      # key indicator at the judge line: rise -> hold -> sink

class FxManager:
    def on_judgment(self, lane, grade, note_time_ms, now_ms): ...
    def on_press(self, lane, now_ms): ...      # always — even on empty presses
    def on_release(self, lane, now_ms): ...
    def on_combo(self, combo, now_ms): ...     # milestone detection inside
    def update(self, now_ms): ...              # expire dead FX, advance state
    # Draw-list getters: pure tuples the GL pass consumes.
    def keybeams(self, now_ms) -> list[tuple[int, float]]          # (lane, intensity)
    def press_markers(self, now_ms) -> list[tuple[int, float, float]]  # (lane, y_lift, alpha)
    def popups(self, now_ms) -> list[tuple[str, int, float]]       # (grade, lane, t)
    def shockwaves(self, now_ms) -> list[tuple[int, str, float]]
    def particles(self, now_ms) -> list[tuple[float, float, float, str, float]]
```

Particle kinematics are closed-form (`pos = f(seed, age)`) — no integration, no
mutation per frame, deterministic and cheap.

### 3.3 GL scene layer order (replaces the current 5-step paint)

Back to front, all under the existing painter's-order/no-depth scheme:

1. **Stage backdrop** — `neon_arcade_stage_background.png` as a screen-filling
   quad behind the board (dark center preserved), tinted by `BeatClock` pulse
   (±6% brightness — felt, not seen).
2. **Atmosphere** — parallax horizon grid (UV-scrolled toward the camera) +
   ~40 drifting dust glints (closed-form positions, additive).
3. Board + lanes (existing two-pass).
4. **Keybeams** — additive vertical gradient quad filling the pressed lane from
   judge line to ~60% track depth; 40 ms flare-in, 120 ms fade after release.
5. **Gear rails** — a few stacked additive quads along the BOARD_LEFT/RIGHT
   edges (wide soft glow under a narrow bright core) with a UV-scrolling energy
   streak; the existing divider lines stay underneath for crispness.
6. Hold bodies + notes — **batched**: one `glBegin(GL_QUADS)` per atlas bind
   via a new `_textured_quad_batch(items)` beside `_textured_quad` (the
   established seam, kept for single quads).
7. **Note approach glow** — additive under-quad swelling in the last 250 ms
   before each note's hit time (only for notes within that window).
8. Judge line (existing hit bar) + per-beat shimmer sweep.
9. **Hit FX stack** — press markers (the rise/hold/sink key indicator, §3.5),
   then shockwave ring (200 ms scale-out), existing impact spark, burst
   particles, grade-tinted.
10. **Judgment popups** — baked glow-text billboards (`PERFECT/GREAT/GOOD/MISS`)
    at the note's lane, scale-pop (ease_out_back, 90 ms) → float up → fade
    (total 480 ms).
11. **Combo billboard** — baked digit-strip texture; combo > 4 shows centered
    above the track mid-depth, `Pulse` scale on every increment; milestone
    (every 50) adds a one-beat gold flare ring.

Baked textures (built once at init by `fx_draw.py`, uploaded via the existing
`upload_surface`): 4 judgment words ×2 sizes, digit strip 0–9, radial glow,
ring, streak glint. Each bake first checks the active skin for an override
image (§4.3); otherwise it is generated procedurally from the skin palette
with `NeonMaterialKit` glow text and radial/ring gradients. All deterministic;
if baking fails the FX pass no-ops.

### 3.4 Event wiring (smallest possible touch on game logic)

- `ScoringEngine` gains `recent_judgments(now_ms)` mirroring `recent_hits`:
  events `(lane, grade, note_time_ms)` appended in `register_hit` **and** in
  `tick()` for timeout misses. `recent_hits` stays (renderer sparks) — the new
  stream feeds `FxManager`. Scoring stays the single owner of hit state.
- `App._handle_playing` / the MIDI poll loop call `fx.on_press(lane, now)`;
  `KEYUP` (currently discarded) maps through the same keymap to
  `fx.on_release`. MIDI note_off stays unwired in v1 — MIDI keybeams just use
  a fixed 150 ms decay (the adapter drops note_off today; do not change it).
- Grade colors come from the skin palette (`palette.judgment`, §4.2).
  Neon-arcade defaults: PERFECT gold `(255, 210, 90)`, GREAT blue
  `(80, 170, 255)`, GOOD white `(225, 235, 255)`, MISS red `(255, 60, 80)`.

### 3.5 How FX animate — staged envelopes, not sprite playback

No effect is "show a PNG". A sprite is only the *shape*; the *motion* comes
from re-issuing the quad every frame with envelope-driven parameters. Our
immediate-mode renderer already redraws everything per frame, so animating
costs nothing extra: each frame, every live FX evaluates its `Envelope`s at
`age = now_ms - born_ms` and feeds the results into the quad's **position,
scale, alpha, and tint**. There are no flipbook frames and no mutable
per-frame state — an FX instance is just `(kind, lane, born_ms, seed)` and
everything else is computed.

**Archetypes.** Each FX kind is a declarative bundle of envelopes in
`effects.py`, so the whole feel of an effect is readable (and tunable) in one
table, never buried in draw code:

```python
HIT_BURST = FxArchetype(
    sprite='glow',
    alpha=Envelope((40, ease_out_cubic, 0.0, 1.0),   # flare in
                   (60, hold, 1.0, 1.0),             # glow
                   (160, ease_in_quad, 1.0, 0.0)),   # fade out
    scale=Envelope((40, ease_out_back, 0.45, 1.0),
                   (220, linear, 1.0, 1.35)),        # keeps swelling as it dies
)
```

**Layered staggering makes the "explosion" feel.** One PERFECT spawns four
primitives whose envelopes overlap but peak at different times — the eye reads
the sequence as one organic burst rather than a stamped image:

| age (ms) | 0–40 | 40–100 | 100–260 | 260–480 |
|---|---|---|---|---|
| white flash quad | flare in (0→1) | snuffs out (1→0) | — | — |
| radial glow | flare in | **holds at peak** | fade out | — |
| shockwave ring | — | scale 0.3→1.6, alpha 1→0.4 | alpha →0 | — |
| burst particles | — | fly outward, full alpha | alpha eases out | — |
| judgment popup | scale-pop in (ease_out_back) | holds | floats up | fades |

Grade scales the whole stack: PERFECT runs it at 1.0 intensity, GREAT 0.7,
GOOD 0.35 (flash layer skipped), MISS swaps to the red palette with no
particles — so accuracy is *felt* before it's read.

**The press marker** (the DJMAX key indicator). On every key press — hit or
empty — a note-sized bright cap spawns at the judge line in that lane and runs
a three-stage lifecycle driven by the press/release events `FxManager` already
receives:

```text
RISE   press .. +50 ms     y: 0 -> 0.35 world units above the judge line
                           (ease_out_cubic), alpha 0 -> 1 in the first 30 ms
HOLD   while key held,     y stays lifted; alpha breathes 1.0 -> 0.85 on a
       min 100 ms          short cosine so it reads "active", not frozen
SINK   release (or hold    y: lifted -> -0.05 (slight dip below the line,
       expiry) .. +120 ms  ease_in_quad), alpha -> 0
```

Early release before RISE completes jumps straight to SINK from the current
interpolated height — envelopes evaluate from *current value*, so there is
never a snap. The marker is drawn as the `{family}/note` sprite at ~70% lane
width with an additive `glow` under-quad, so it visually echoes "a note was
pressed here". `press_markers(now)` returns `(lane, y_lift, alpha)` and the
GL pass lifts the quad along +Y (toward the camera-up) at the hit-bar Z —
the same cheap math as every other quad.

The same envelope vocabulary drives everything else in this spec — keybeam
flare/decay, judgment popup pop/float/fade, countdown ring, combo pulse,
results count-ups — which is why `anim.py` lands first and is tested to the
edge cases (zero-length segments, retrigger mid-flight, age past total).

---

## 4. Plugin Skin System

Today every visual constant is welded into code: atlas rects in
`src/ui/atlas.py`, colors scattered as module constants, the stage/jacket/tile
images as hardcoded paths. Re-skinning the game means editing five modules.
Phase 6 inverts this: **a skin is a folder of data**, the engine consumes a
fixed *asset-role contract*, and dropping a new folder under `resources/skins/`
re-themes the whole game with **zero code change**.

### 4.1 Skin package layout

```text
resources/skins/<skin-id>/
├── skin.json                  # the manifest — required, everything else flows from it
├── atlas.png                  # primary sprite sheet (regions defined in the manifest)
├── stage_background.png       # optional standalone images …
├── jacket_placeholder.png
├── panel_tile.png
├── menu_background.png
├── fx/                        # optional FX sprite overrides (else procedurally baked)
│   ├── keybeam.png  ring.png  glow.png  glint.png  dust.png
│   ├── judgment_perfect.png  judgment_great.png  judgment_good.png  judgment_miss.png
│   └── digits.png
└── fonts/
    └── main.ttf               # optional font override (else the sysfont stack)
```

The current neon-arcade look becomes the first pack:
`resources/skins/neon-arcade/` is created by **migrating** the existing
`neon_texture_atlas.png`, the three standalone `resources/ui/*.png` images, and
the measured rect/nine-slice numbers from `atlas.py` +
`neon_arcade_skin_resources.json` into a `skin.json`. That catalog JSON is then
retired (superseded by the manifest).

### 4.2 The manifest — `skin.json`

One JSON file defines everything. Schema (format version 1):

```json
{
  "format": 1,
  "id": "neon-arcade",
  "name": "Neon Arcade",
  "author": "MidiMania",

  "images": {
    "atlas": "atlas.png",
    "stage_background": "stage_background.png",
    "jacket_placeholder": "jacket_placeholder.png",
    "panel_tile": "panel_tile.png",
    "menu_background": null
  },

  "palette": {
    "blue":  { "core": [40, 120, 255], "text": [150, 205, 255], "glow": [30, 175, 255] },
    "white": { "core": [225, 235, 255], "text": [235, 245, 255], "glow": [200, 220, 255] },
    "red":   { "core": [255, 60, 90],  "text": [255, 200, 210], "glow": [255, 48, 70] },
    "judgment": { "perfect": [255, 210, 90], "great": [80, 170, 255],
                  "good": [225, 235, 255], "miss": [255, 60, 80] },
    "ui": { "text": [235, 245, 255], "muted": [120, 170, 220],
            "gold": [255, 210, 90], "bg": [5, 8, 18] }
  },

  "regions": {
    "blue/lane":        { "rect": [34, 72, 82, 498] },
    "blue/note":        { "rect": [389, 158, 84, 36] },
    "blue/score_panel": { "rect": [740, 67, 484, 101], "nine_slice": [42, 24, 50, 26] },
    "blue/impact_spark":{ "rect": [560, 1036, 110, 102], "alpha_key": true },
    "rank/rank_s":      { "rect": [394, 1177, 57, 60] }
  },

  "fx": {
    "keybeam": "fx/keybeam.png",
    "ring": null,
    "judgment_perfect": null,
    "digits": null
  }
}
```

Rules:

- **`format`** — loader accepts `format <= 1`; a newer number logs a warning
  and the pack is skipped (forward compatibility).
- **`regions`** — flat `"family/name"` keys; `rect` is `[x, y, w, h]` in atlas
  pixel space, top-left origin (exactly today's `ATLAS_RECTS` convention).
  Optional per-region keys: `nine_slice: [left, top, right, bottom]` (panels)
  and `alpha_key: true` (legacy black-background FX sprites — the loader
  applies the existing near-black suppression; **new art should ship true
  alpha instead**).
- **`palette`** — the named colors that drawn fallbacks, glow text, judgment
  popups, and FX tints consume. Family entries (`blue/white/red`) carry
  `core/text/glow`; `judgment` and `ui` are fixed role groups.
- **`fx`** — per-sprite override paths; `null`/absent means "bake procedurally
  from the palette" (§4.4). Every FX role has a procedural default, so a skin
  with an empty `fx` block is complete.
- Unknown keys anywhere are **ignored**, so format 1 packs keep loading under
  future loaders.

### 4.3 The asset-role contract

This is the fixed vocabulary the engine consumes. A skin *fills roles*; it
cannot invent new ones (new roles require code that draws them — that is the
honest boundary of "no code change"). `●` = required for a complete pack,
`○` = optional with a stated fallback. All images are **PNG, straight
(non-premultiplied) alpha, sRGB**; atlas max 4096×4096.

**Atlas regions, per color family** (`blue`, `white`, `red` — the three lane
roles the game logic assigns; which lane gets which family stays in code):

| Role | Req | Used by | Art guidance |
|---|---|---|---|
| `{f}/lane` | ● | GL lane overlay | tall strip ≈1:6, tileable vertically |
| `{f}/note` | ● | falling tap notes | wide tile ≈2.3:1, readable at 30 px |
| `{f}/hold` | ● | hold bodies | vertical body, stretches lengthwise |
| `{f}/impact_spark` | ● | hit flash (additive) | centered burst on transparency |
| `{f}/glint_tiny` | ○ → impact_spark scaled | 2D spark garnish | loose particle cluster |
| `{f}/key` | ○ → drawn cap | key caps (future) | rounded cap face |

**Atlas regions, singletons:**

| Role | Req | Used by | Notes |
|---|---|---|---|
| `blue/hit` | ● | judge line | wide thin bar, glows |
| `blue/score_panel` `red/combo_panel` `blue/song_info_panel` `blue/gauge_panel` `blue/small_stat_box` | ● | HUD frames | each needs `nine_slice` borders |
| `blue/generic_wide_panel` | ○ → drawn frame | menu/results panels | nine-slice |
| `blue/gauge_empty` `blue/gauge_filled` `blue/gauge_overlay_glow` | ● | accuracy gauge | horizontal bars, equal width |
| `blue/decor_line` `blue/decor_corner` `blue/arrows` `blue/screw_decal` `blue/life_icon` `blue/multiplier_chip` `blue/meter_piece_full` | ○ → omitted | decorative accents | absence simply draws nothing |
| `rank/rank_c` … `rank/rank_s_plus` | ○ → drawn letter | results badge | ≈1:1 |

**Standalone images** (`images` block):

| Role | Req | Fallback | Guidance |
|---|---|---|---|
| `atlas` | ● | flat-color rendering (today's path) | the sheet above |
| `stage_background` | ○ | solid `ui.bg` clear color | ≥1366×768, dark center band where the track sits |
| `jacket_placeholder` | ○ | flat dark box | square, ≥512² |
| `panel_tile` | ○ | procedural noise tile | ≥256², low-contrast, tileable |
| `menu_background` | ○ | stage_background, else `ui.bg` | ≥1366×768 |

**FX sprites** (`fx` block — all `○`, every one has a procedural bake):

| Role | Procedural default (from palette) | Override format |
|---|---|---|
| `keybeam` | vertical white→transparent gradient, tinted per family at draw | ≈64×256, bright at bottom |
| `glow` | radial gradient | ≈128², centered |
| `ring` | anti-aliased circle outline | ≈128², centered |
| `glint` | 4-point star | ≈32² |
| `dust` | soft dot | ≈16² |
| `judgment_{perfect,great,good,miss}` | glow text in `palette.judgment` colors, skin font | ≈480×96, word centered |
| `digits` | glow digits, skin font | **single row, 10 equal-width cells, 0–9 left→right**; cell aspect ≈0.62:1 |

**Font** (`fonts/main.ttf`): used for all baked text sprites and HUD text;
fallback is the current `consolas,menlo,monospace` sysfont stack.

### 4.4 Loading, selection, and the fallback chain

```python
# src/ui/skin_pack.py
class SkinPack:
    @classmethod
    def load(cls, skin_dir: str) -> "SkinPack": ...   # parse + validate manifest
    def rect(self, family, name) -> tuple | None
    def uv(self, family, name) -> UV | None           # same math as atlas.uv today
    def nine_slice(self, family, name) -> Border | None
    def color(self, group, role) -> Color             # palette with hard defaults
    def image_path(self, role) -> str | None          # resolved absolute path
    def fx_path(self, role) -> str | None
    def font_path(self) -> str | None

def discover() -> dict[str, str]                      # skin-id -> directory
def active() -> SkinPack                              # selection, cached
```

- **Selection:** `MIDIMANIA_SKIN=<id>` env var → else the id stored in
  `resources/skins/active.json` (written by a future menu setting) → else
  `neon-arcade` → else the first discovered pack. No pack at all → every
  consumer's existing flat-color fallback path runs (the game today already
  survives a missing atlas; that behavior is preserved verbatim).
- **Per-asset fallback chain**, applied at load, never at frame time:
  *active skin → default (`neon-arcade`) pack → procedural/drawn fallback.*
  A skin therefore only needs to override what it changes — a "red theme"
  pack can ship one atlas and no FX folder.
- **`atlas.py` becomes a facade**: `uv()`/`nine_slice()` delegate to
  `active()`. Every existing consumer (`NeonMaterialKit`, `AtlasTexture`,
  `NeonArcadeSkin`, renderer) keeps its API; `gl_textures.DEFAULT_ATLAS` and
  the hardcoded `resources/ui` paths in `skin.py` are replaced by
  `SkinPack.image_path()` lookups. `tests/test_atlas.py` migrates to
  validating the default pack's manifest (names exist, UVs in [0,1], rects
  inside the image, unknown names → None).
- **Validation at load**: rect bounds checked against the actual atlas size;
  malformed regions are dropped individually with one console line each —
  a bad region degrades that one element, never the pack, never the game.
- Manifest parsing and palette/region lookup are pure (headless-testable);
  image loading uses the existing `load_optional_ui_image` tolerance.

### 4.5 Authoring & validation tooling

`tools/validate_skin.py <dir>` — the skin author's contract checker, run as
CLI and in CI for bundled packs:

1. JSON parses; `format` supported; `id` matches the directory name.
2. Every referenced file exists; every image decodes as PNG-with-alpha.
3. Region rects inside atlas bounds; nine-slice borders smaller than their rect.
4. Coverage report: which `●` roles are missing (errors), which `○` roles fall
   back and to what (info) — so an author sees exactly what their pack will do.
5. `--capture` flag: renders the offscreen verification set (§7) with the pack
   active and writes PNGs beside it — visual proofing without launching the game.

---

## 5. Implementation Plan — seven shippable phases

Per the established workflow: each phase is its own branch
(`phase/6.N-...`), TDD where state is pure, one commit per milestone, offscreen
captures before merge.

### Phase 6.0 — Skin pack foundation (§4)

1. `src/ui/skin_pack.py`: manifest schema, loader, validation, discovery,
   selection; tests for parse/validate/fallback/selection (pure, headless).
2. Create `resources/skins/neon-arcade/`: migrate the atlas, the three
   `resources/ui` standalone images, and the `ATLAS_RECTS` +
   `NINE_SLICE_BORDERS` numbers into its `skin.json`; retire
   `neon_arcade_skin_resources.json`.
3. `atlas.py` → facade over `skin_pack.active()`; swap the hardcoded image
   paths in `gl_textures.py` / `skin.py` for `image_path()` lookups; migrate
   `tests/test_atlas.py` to validate the default pack.
4. `tools/validate_skin.py` (validation core shared with the loader).

**DoD:** suite green; captures pixel-identical to pre-phase (migration is
invisible); a minimal fixture skin under `tests/fixtures/` selected via
`MIDIMANIA_SKIN` visibly changes a capture with zero code change; deleting
`resources/skins/` entirely still boots into flat-color rendering.

### Phase 6.1 — Foundation: anim + effects core + judgment stream

1. `src/ui/anim.py` with full unit tests (`tests/test_anim.py`) — easing edge
   values, Envelope segment boundaries / zero-length segments / age past
   total, Pulse retrigger, RollingValue convergence, Timeline segment math,
   BeatClock phase wrap.
2. `ScoringEngine.recent_judgments` + tests (hit grades, tick-miss events,
   sweep semantics identical to `recent_hits`).
3. `src/ui/effects.py` `FxManager` + tests (`tests/test_effects.py`):
   keybeam and press-marker press/release lifecycles (including early release
   mid-RISE, §3.5), popup expiry, deterministic particle positions, milestone
   detection, caps (§8).
4. `Renderer._textured_quad_batch` + conversion of the note/hold loops; GL
   smoke test extension proving a frame still renders.

**Definition of done:** suite green headless; standalone GL tests pass; a
capture renders pixel-identical playfield (batching is invisible).

### Phase 6.2 — Playfield juice (the core DJMAX feel)

1. `src/ui/fx_draw.py`: baked textures + draw passes for keybeams, press
   markers, shockwaves, particles, popups (layer order §3.3 items 4, 9, 10),
   each animated by its archetype envelopes (§3.5).
2. Wire `FxManager` into `App` (press/release/judgments/combo) and
   `Renderer.render(chart, now, sparks, fx=None)` — `fx=None` keeps every
   existing test and the single-chart `run()` path working unchanged.
3. Note approach glow (item 7).
4. Combo billboard (item 11) with digit strip.

**DoD:** captures show — pressing an empty lane flares the keybeam; a PERFECT
shows gold popup + ring + particles; combo pulses above the track. Headless
suite untouched/green.

### Phase 6.3 — Stage atmosphere (kill the void)

1. Stage backdrop quad (Phase 5 deferral honored: dark playfield center
   verified by capture histogram of the lane area).
2. Parallax grid + dust layer, UV-scroll driven by `now_ms`.
3. Gear side rails with flowing streak.
4. `BeatClock` pulse on backdrop tint + judge-line shimmer.

**DoD:** capture at t=0 vs t=2s shows background motion; lane-area mean
luminance within +10% of pre-phase capture (readability guard).

### Phase 6.4 — HUD motion

1. `HudOverlay.render(..., now_ms)` (default param; old signature keeps
   working) threaded from `App`/`run()`.
2. Combo pop (`Pulse` scale on the combo text), score `RollingValue`,
   gauge `RollingValue` + glow breathing, FULL COMBO gold shimmer.
3. Countdown: scale-in + fade ring per second, "GO!" flash at 0.
4. Tests: rolling/pulse state via injected times; HUD transparency tests
   unchanged.

### Phase 6.5 — Menu restyle + screen transitions

1. Menu: `NeonArcadeSkin` panels (song list panel, right-side detail panel
   with jacket via `_load_jacket`, mode chips on `small_stat_box` frames),
   animated backdrop (reuse 6.3 layers under a darkened scrim), eased list
   scroll (selection offset animates via `RollingValue`), selected-row glow
   pulse.
2. `App` crossfade: 220 ms fade-through-black on every screen change
   (a `Timeline` + fullscreen alpha quad drawn last in `render()`).
3. Menu keeps full keyboard behavior; all `SongMenu` logic tests untouched
   (drawing-only changes; selection state grows an animated-offset shadow
   value, logic value stays authoritative).

### Phase 6.6 — Results spectacle

1. `Timeline` reveal: header (0–200 ms) → judgment counters count up
   (staggered, 200–900 ms, eased) → score roll (600–1200 ms) → rank badge
   slam (`ease_out_back` scale 2.4→1.0 + white flash) → prompt fade-in.
2. S rank: ~60 deterministic gold confetti glints falling for 2 s; FULL COMBO
   banner if applicable.
3. R/Enter during reveal skips to the completed state (standard rhythm-game
   affordance).

### Phase 6.7 (optional, last) — True bloom post-processing

FBO render-to-texture + 2-pass GLSL blur + additive recombine. Gated on a GL
capability probe at startup; any failure → silent fallback to the direct path.
Env escape hatch `MIDIMANIA_BLOOM=0`. This is the only phase touching shaders;
everything before it must already look great without it.

---

## 6. Why this shape (alternatives considered)

- **Shader-first rewrite** (modern GL, instancing, bloom from day one):
  highest ceiling, but torpedoes the headless-test discipline, the flat-color
  fallback story, and risks weeks of plumbing before any visible payoff.
  Rejected as the *first* move; kept as the *last* (6.7).
- **HUD-layer FX** (draw popups/beams on the pygame overlay): simpler, but
  breaks perspective (effects wouldn't sit *on* the track), fights the HUD
  center-transparency contract, and pygame per-pixel alpha blits at 1366×768
  are slower than additive GL quads. Rejected.
- **Chosen: baked-sprite additive GL layering** — matches the existing
  `_textured_quad` seam (built for exactly this, per the Phase 3.3 design),
  keeps state pure/testable, ships visible improvement per phase.

## 7. Verification

Every phase:

```powershell
python -m unittest                                  # full headless suite
python -m unittest tests.test_gl_renderer           # standalone, real GL
python -m unittest tests.test_gl_textures
```

Plus offscreen captures (HIDDEN GL window + glReadPixels) into `tmp/`:
gameplay at three timestamps (idle lane / active hit / miss), menu, countdown,
results at four reveal stages. Compare against prior captures before merging.
New pure modules (`anim`, `effects`) target exhaustive unit coverage — they are
plain math.

## 8. Performance budget (hard caps in code)

| FX | Cap | Cost ceiling |
|---|---|---|
| Keybeams | lane_count | 1 quad each |
| Press markers | lane_count | 2 quads each (cap + glow) |
| Popups | 12 live | 1 quad each |
| Shockwaves | 12 live | 1 quad each |
| Burst particles | 96 live | 1 quad each |
| Dust/atmosphere | 40 | 1 quad each |
| Confetti (results) | 60 | 1 quad each |

Worst case ≈ 250 FX quads + batched notes — under 20% of the 2,000-quad
budget. `FxManager.update` drops oldest-first past caps. If a profile shows a
frame > 12 ms on the dev machine, particle caps halve before anything else.

## 9. Guardrails

- Note/judgment **readability beats spectacle**: no effect may raise lane-area
  background luminance >10% or cover an unhit note with >40% additive alpha.
- No gameplay changes: scoring numbers, windows, and engine states are
  untouched; FX consume events, never produce them.
- All new visual state is a pure function of `current_ms` + seeds — no
  `random()` at frame time, no wall clock.
- Every baked asset and every FX pass must no-op safely when unavailable.
- Atlas rects, nine-slice borders, and colors live only in skin manifests
  (`skin.json`, §4.2); FX timing constants live in `effects.py`/`anim.py`.
  Neither gets scattered through draw code.
- The asset-role contract (§4.3) is fixed per format version: skins fill
  roles, they never define new ones. Unknown manifest keys are ignored.
- A broken skin can never crash or soft-lock the game: per-asset fallback
  (active skin → neon-arcade → procedural/drawn) is resolved at load time,
  with one console line per dropped asset.
- 49key+ MIDI mode: keybeams/popups scale with lane width; if a lane is
  < 24 px on screen, popups consolidate to a single center-track position.
- Do not change `src/input/midi_input.py` note_off behavior in this phase.
