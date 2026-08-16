# McGraw Girls Backgrounds 🌈

A fun, colorful web app that lets kids browse and pick from **1040
backgrounds** across 56 categories — rainbows, unicorns, dinosaurs,
mermaids, space, sports, huskies, dogs, horses, dragons, robots, pirates,
and lots more. Every background comes in a flat **illustrated** style, 15
animal/nature-heavy categories also have a second, more detailed
**realistic style** tier (soft lighting, texture, depth-of-field-style
backdrops), and the Flowers & Florals category also has 40 genuine
**real photos** — switchable via the style tabs.

Open `index.html` in a browser (or serve the folder with any static file
server) — no build step, no dependencies.

```
python3 -m http.server 8080   # then visit http://localhost:8080
```

## Features

- Scrollable, responsive thumbnail grid (2–6 columns depending on screen size)
- Tap a thumbnail to preview it full screen, with a smooth zoom-in transition
- "Set as Background" button with confetti + a celebratory chime (visual/audio
  feedback only — this is a picker, not a real device-background setter)
- Swipe or use the arrow buttons to move between previews; pinch to zoom
- Two rows of horizontally-scrolling tabs: art style (All / Illustrated /
  Realistic) and category (56 categories + Favorites)
- Search box matching titles, categories, and a rich per-image tag set
- Heart a background to favorite it — favorites persist in `localStorage`
- "Random" button jumps straight into a random background preview
- Download button saves the current background's SVG file
- Optional sound-effect toggle (also saved in `localStorage`)

## Project structure

```
index.html              Markup / app shell
styles.css               All styling (kid-friendly, rounded, animated)
app.js                    App logic (grid, search, favorites, preview, confetti)
images/
  backgrounds.json        Metadata for every background (id, title, category, style, tags, credit…)
  backgrounds/<category>/ 1000 original SVG artworks (6-45 per category) + 40 real JPG photos
                           (images/backgrounds/flowers-florals/photos/)
  icons/                  UI icon set (heart, star, arrows, search, sound, …)
scripts/
  generate_backgrounds.py     Procedurally generates every illustrated/realistic-style SVG
                               + merges in the real photos + writes backgrounds.json
  import_real_photos.py       Downloads and processes the real photos (see below)
  real_photos_picks.json      Hand-reviewed list of which source photos to use
  real_photos_manifest.json   Generated metadata for the real photos (feeds generate_backgrounds.py)
```

## About the artwork

Most backgrounds are **original, procedurally-generated SVGs** — built from
simple vector shapes (gradients, circles, stars, hearts, flowers, animal
faces, etc.) composed by `scripts/generate_backgrounds.py`. Nothing is
sourced from outside the repo, so there are no licensing concerns, and since
they're vector graphics they stay crisp at any iPad resolution.

To regenerate or extend the set (e.g. add more variants per category):

```
python3 scripts/generate_backgrounds.py
```

Re-running is deterministic (each variant is seeded), and it overwrites
`images/backgrounds/**/*.svg` and `images/backgrounds.json` in place. It also
re-merges the real photo metadata (see below) if present.

### Real photos (Flowers & Florals)

The 40 `style: "photo"` backgrounds are genuine photographs — both landscape
(2732×2048) and portrait (2048×2732) JPGs — from the TensorFlow
["flower_photos"](https://www.tensorflow.org/datasets/catalog/tf_flowers)
dataset: ~3,670 flower photos scraped from Flickr and released under
**Creative Commons Attribution 2.0 (CC BY 2.0)**, with every photo's
original photographer and Flickr URL documented in the dataset's own
`LICENSE.txt`. Each background's `credit` field in `backgrounds.json`
carries that attribution, and it's shown in the app's preview view.

The source dataset has a handful of mislabeled/inappropriate photos (a
picture of a tractor labeled "tulips," a picture of a dog among the roses,
etc.) — `real_photos_picks.json` is a hand-reviewed selection that skips
those, checked against a contact-sheet preview before being committed.
Source photos are Flickr's smaller renditions (~500px), upscaled to fill
an iPad-resolution canvas, so they're a bit softer than native iPad
wallpaper resolution up close but read well at normal viewing size.

To re-run the import (re-downloads the ~230MB source archive from
`storage.googleapis.com`, no dependencies beyond Pillow):

```
pip install Pillow
python3 scripts/import_real_photos.py
python3 scripts/generate_backgrounds.py
```

Real photos for other categories weren't added: this dataset only covers
flowers, and every other legitimate real-photo/stock-photo host tested
(Wikimedia Commons, NASA, Unsplash, Pexels, Pixabay) was unreachable from
the environment this was built in.
