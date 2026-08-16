# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A kids' iPad background-picker web app ("McGraw Girls Backgrounds"): a
static site with no build step, no framework, no dependencies. `index.html`
+ `styles.css` + `app.js` is the entire runtime. Everything else in the
repo is either shipped image assets or Python tooling that generates them.

## Commands

There is no package manager, build, lint, or test-runner config in this
repo. Common tasks:

```
# Run the app locally
python3 -m http.server 8080   # visit http://localhost:8080

# Regenerate the procedural artwork (SVG, as an internal drawing step)
python3 scripts/generate_backgrounds.py

# Convert generated background SVGs -> JPG and delete the SVGs (required
# after the step above -- see "Image pipeline" below)
python3 scripts/rasterize_backgrounds.py

# Convert UI icon SVGs -> transparent PNG and delete the SVGs (run after
# hand-editing any icon in images/icons/)
python3 scripts/rasterize_icons.py

# Re-import the real flower photos (rarely needed; re-downloads a ~230MB
# archive)
pip install Pillow
python3 scripts/import_real_photos.py
python3 scripts/generate_backgrounds.py

# Re-import the real Open Images photos (rarely needed; downloads ~60MB of
# metadata CSVs + the source JPGs into a gitignored .cache/, so a second run
# is nearly instant)
pip install Pillow
python3 scripts/import_openimages_photos.py
python3 scripts/generate_backgrounds.py
```

`rasterize_backgrounds.py` and `rasterize_icons.py` both require
Playwright with a Chromium build. In this environment, launch with
`executable_path="/opt/pw-browsers/chromium"` — the default headless-shell
path Playwright picks does not exist here (already handled inside both
scripts, conditionally, so plain `playwright install` should not be run).

There is no automated test suite. Manual verification is done by serving
the app with `python3 -m http.server` and driving it with Playwright
(screenshot the grid, open a preview, exercise search/favorites/tabs,
check `document.images` for any `naturalWidth === 0`).

## Image pipeline (important, easy to get wrong)

**The repo ships zero SVG files.** Every image under `images/` must be JPG
or PNG. But the art is *authored* as SVG and rasterized as a separate
step — don't "fix" this by trying to make `generate_backgrounds.py` emit
JPG directly:

1. `scripts/generate_backgrounds.py` composes each background procedurally
   as SVG (vector shapes are just a convenient way to build the art) and
   writes `images/backgrounds/<category>/<slug>.svg` + `images/backgrounds.json`
   (with `filename` fields pointing at the `.svg` files).
2. `scripts/rasterize_backgrounds.py` reads `images/backgrounds.json`,
   renders every `.svg` entry to a `.jpg` via headless Chromium
   (`page.screenshot(type="jpeg")`), deletes the source `.svg`, and rewrites
   `backgrounds.json` so `filename` points at the `.jpg`.
3. UI icons in `images/icons/` follow the identical pattern via
   `scripts/rasterize_icons.py`, except icons render to transparent PNG
   (`omit_background=True`) rather than opaque JPG, since they sit inside
   colored buttons/pills rather than filling the frame.

So after step 1 alone, the working tree will contain `.svg` files again —
**always run the matching rasterize script before committing**, and check
`find images -iname '*.svg'` returns nothing before finishing any task that
touches the art pipeline.

The 354 real photos are the exception to steps 1-2 — they're already JPG,
so the rasterize step leaves them alone. Each import writes its own
manifest under `scripts/`, and `generate_backgrounds.py`'s `main()` merges
every manifest in its list (in order, appended after the generated
entries):

- 40 flowers (Flowers & Florals) from the TensorFlow `flower_photos`
  dataset (CC BY 2.0) — `import_real_photos.py` → `real_photos_manifest.json`.
- 314 photos across 22 categories from Google's Open Images dataset (CC BY
  2.0) — `import_openimages_photos.py` → `openimages_photos_manifest.json`.

Both importers are pinned to a hand-reviewed `*_picks.json`, so re-running
them is reproducible and never re-rolls the selection. **Adding a third
photo source means adding its manifest to that list in `main()`** — nothing
else in the generator needs to change.

Because photo entries are appended after all generated entries, adding or
re-running a photo import does not require re-rendering the 1000 procedural
backgrounds. Rebuild `backgrounds.json` as *generated entries (everything
with `style != "photo"`, in order) + each photo manifest in the same order
`main()` lists them* and the result is identical to a full
`generate_backgrounds.py` + `rasterize_backgrounds.py` run. Verify it rather
than trusting it: run `main()` with `OUT_DIR`/`JSON_PATH` pointed at a temp
directory and diff the two, normalising the `.svg`/`.jpg` extension on
generated entries.

## Adding real photos (`import_openimages_photos.py`)

Open Images is the only usable real-photo source reachable from this
environment, and it is the one to reach for when asked for more real
photos. Network reality, checked rather than assumed: the egress policy
allows `storage.googleapis.com` (the metadata CSVs), `s3.amazonaws.com`
(the CVDF image mirror, 1024px on the long edge) and
`github.com`/`raw.githubusercontent.com`. Wikimedia Commons, Unsplash,
Pexels, Pixabay, Openverse, Flickr and `thor.robots.ox.ac.uk` are all
blocked — don't burn time re-probing them, and don't try to route around a
403 from the proxy. Stanford Dogs and the Kaggle Cats & Dogs subset are
reachable but research-only, so they must not be shipped.

Adding a batch, end to end:

1. **Harvest candidates** from the validation + test subsets by
   cross-referencing `{subset}-annotations-human-imagelabels.csv` (the
   ~20k-class image-level vocabulary — Kitten, Rose, Rainbow, Jellyfish, …;
   `oidv6-class-descriptions.csv` maps names to `/m/...` ids) with
   `{subset}-annotations-bbox.csv` (the 600 boxable classes, which give
   subject area). Filters that carry their weight: license must be exactly
   CC BY 2.0; reject any image labelled `Person` `/m/01g317`, `Human face`
   `/m/0dzct`, `Man`, `Woman`, `Girl`, `Boy`, `Human body`, `Human head`,
   `Human hand`, `Human arm`, `Text` `/m/07s6nbt`, `Poster` `/m/01n5jq` or
   `Car` `/m/0k4j`; and for boxable subjects require a box covering ≥10% of
   the frame.
2. **Review every candidate by eye on contact sheets** — this is not
   optional and cannot be automated away. Open Images is Flickr snapshots:
   expect to throw away roughly two thirds for watermarks, date stamps and
   caption overlays, collages, product/museum shots, craft/plush/CGI
   stand-ins for the real animal, brand logos, nursing or newborn litters,
   dark or blurry frames, and photos where a person dominates.
3. **Append picks** to `scripts/openimages_photos_picks.json` — one object
   per photo with `image_id`, `subset`, `category`, `subject` and a
   hand-written `title`. Titles are what the app shows and what the output
   filename is slugified from, so keep them stable: changing a title
   renames its JPG.
4. **Register any new category** in the importer's `CATEGORIES` map
   (display name + bonus search tags, mirroring `CATS`/`CATEGORY_TAGS` in
   `generate_backgrounds.py`). An unknown slug raises rather than silently
   defaulting.
5. Run the importer, then rebuild `backgrounds.json` (see above).

Downloads are cached in a gitignored `.cache/open-images/`, so re-running
is cheap. Output orientation follows the source's own aspect ratio — never
force portrait on a landscape source, it crops the subject away.

## `generate_backgrounds.py` architecture

This one file (~3900 lines) is the entire art generator. Skimming it top
to bottom:

- **Low-level SVG builder**: an `Svg` class (`defs`/`body` lists,
  `linear_gradient()`, `radial_gradient()`, `blur_filter()`, `render()`)
  plus primitive helpers (`rect`, `circle`, `ellipse`, `polygon`, `path`,
  `line`, `group`) and ~80 named shape helpers (`heart_shape`,
  `flower_shape`, `paw_shape`, `dino_shape`, `husky_face_shape`, etc.) that
  each draw one motif from primitives.
- **Realism helpers** (`shadow_ellipse`, `glow_highlight`, `vignette`,
  `fur_texture`, `bokeh_backdrop`, `realistic_scene()`) — used by the
  `style="realistic"` variants to add soft shadows, blur-based bokeh
  backdrops, and texture strokes on top of the same shape helpers.
- **Category registry**: `CATS` (list) / `CATS_BY_SLUG` (dict) built up by
  calling `cat(slug, name, variants, style="illustrated")` once per
  category/style combo. Calling `cat()` again for a `slug` that already
  exists *appends* to that category's `variants` instead of replacing it —
  this is how a category ends up with both `illustrated` and `realistic`
  variants (two separate `cat()` calls, same slug, different `style`).
  `variants` is a list of `(title, builder_fn, style)` tuples.
- **Scene factories** used to build those `variants` lists compactly:
  `scene()`, `titled_variants()`, `multi_kind_scene()` — each takes a base
  builder function plus lists of moods/palettes/skies and produces many
  titled variants from one call.
- **Tagging**: `CATEGORY_TAGS` (dict of slug -> bonus search tags) and
  `title_keywords(title)` (extracts extra tags from each variant's title)
  are combined in `main()` to build each entry's `tags` array — this is
  what backs the app's search box.
- **`main()`**: walks `CATS`, renders every variant's SVG via a
  `random.Random(f"{slug}-{i}-{title}")` seed (determinism matters — see
  below), writes the files, builds `backgrounds.json`, then merges in
  `real_photos_manifest.json` if present.

**Determinism**: every variant must be seeded from a per-variant
`random.Random(...)` instance (via the `rng` argument threaded through
scene factories and shape helpers), never the global `random` module —
using the unseeded global module makes re-running the generator produce
different output for the same title, which has caused bugs before
(`popcorn_shape`/`giraffe_shape` both had to be fixed to take a seeded
`local_rng` instead of the module-level `random`).

## App architecture (`app.js`)

Single IIFE, `state` object holds everything: `all` (full background
list), `categories`, `filtered`, `activeCategory`, `activeStyle`,
`searchTerm`, `favorites` (persisted to `localStorage` under
`mcgrawGirlsBackgrounds.favorites`), `soundOn`
(`mcgrawGirlsBackgrounds.soundOn`), `previewIndex`, `renderedCount`.

- Backgrounds are loaded once from `images/backgrounds.json` at startup.
- The grid (up to 1040 cards) renders in batches of `BATCH_SIZE = 60` via
  `appendNextBatch()`, triggered by an `IntersectionObserver` watching a
  `.grid-sentinel` element (`onLoadMoreIntersect()`) — rendering everything
  synchronously on load blocks the main thread for several seconds, hence
  the batching.
- Style tabs (`STYLE_LABELS`: All / Illustrated / Realistic / Real Photos)
  and category tabs both filter `state.all` into `state.filtered`;
  `applyFilters()` is the single place that recomputes and re-renders.
- Preview view is a separate full-screen section (`#preview-view`), not a
  route — toggled via `hidden`. Prev/next arrows and swipe gestures walk
  `previewList` (the currently filtered list, so preview navigation stays
  within the active filter/search).
- "Set as Background" (`el.setBgBtn` handler): no browser API can set a
  device's actual wallpaper, so this fetches the current image as a blob
  and uses the Web Share API (`navigator.canShare({files})` /
  `navigator.share`) to open iOS's native share sheet, so the user can Save
  to Photos and then use Photos' own Share -> Use as Wallpaper. Falls back
  to a plain `<a download>` when Web Share with files isn't supported. A
  toast (`showSetBgToast`) explains the next step for each outcome
  (`shared` / `downloaded` / `cancelled` / `error`).
- Google Fonts are loaded lazily from `app.js` (`requestIdleCallback`,
  falling back to `setTimeout`) *after* the grid has already rendered —
  never add a blocking `<link rel="stylesheet">` for fonts in
  `index.html`, since some browsers hold script execution on a pending
  stylesheet load and a slow/unreachable font host must not delay the app.

## PWA / Home Screen

`manifest.webmanifest` + the `apple-mobile-web-app-*` meta tags and
`apple-touch-icon`/favicon `<link>`s in `index.html`'s `<head>` control
"Add to Home Screen" behavior. The Home Screen label is controlled by
**two places that must stay in sync**: `apple-mobile-web-app-title` in
`index.html` and `short_name` in `manifest.webmanifest`.

`env(safe-area-inset-*)` CSS custom properties (`--safe-top` etc. in
`styles.css`'s `:root`) are used throughout the fixed topbar/tabs/bottombar
so standalone (full-screen, no browser chrome) mode on notched iPads
doesn't overlap the status bar or home indicator — remember to keep these
in any `@media` overrides that touch those elements' padding, since an
override that resets padding without re-adding the safe-area term will
silently reintroduce the overlap bug.
