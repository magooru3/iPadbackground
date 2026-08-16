# McGraw Girls Backgrounds 🌈

A fun, colorful web app that lets kids browse and pick from **1354
backgrounds** across 56 categories — rainbows, unicorns, dinosaurs,
mermaids, space, sports, huskies, dogs, horses, dragons, robots, pirates,
and lots more. Every background comes in a flat **illustrated** style, 15
animal/nature-heavy categories also have a second, more detailed
**realistic style** tier (soft lighting, texture, depth-of-field-style
backdrops), and 22 categories also have genuine **real photos** — 354 of
them, from puppies and kittens to rainbows, jellyfish and the Milky Way —
switchable via the style tabs.

Open `index.html` in a browser (or serve the folder with any static file
server) — no build step, no dependencies.

```
python3 -m http.server 8080   # then visit http://localhost:8080
```

## Features

- Scrollable, responsive thumbnail grid (2–6 columns depending on screen size)
- Tap a thumbnail to preview it full screen, with a smooth zoom-in transition
- "Set as Background" button with confetti + a celebratory chime, then shares
  or downloads the image so it can be set as the actual iPad wallpaper from
  Photos (see "Setting the real wallpaper" below)
- Swipe or use the arrow buttons to move between previews; pinch to zoom
- Two rows of horizontally-scrolling tabs: art style (All / Illustrated /
  Realistic / Real Photos) and category (56 categories + Favorites)
- Search box matching titles, categories, and a rich per-image tag set
- Heart a background to favorite it — favorites persist in `localStorage`
- "Random" button jumps straight into a random background preview
- Download button saves the current background's JPG/PNG file
- Optional sound-effect toggle (also saved in `localStorage`)
- Installable as a Home Screen app ("Backgrounds" icon) with its own launch
  icon, splash color, and full-screen standalone display

## Project structure

```
index.html              Markup / app shell
styles.css               All styling (kid-friendly, rounded, animated)
app.js                    App logic (grid, search, favorites, preview, confetti)
manifest.webmanifest      PWA manifest (Home Screen name/icon/theme color)
images/
  backgrounds.json        Metadata for every background (id, title, category, style, tags, credit…)
  backgrounds/<category>/ 1000 original JPG artworks (6-45 per category) + 354 real JPG photos
                           (in the photos/ subfolder of 22 of the categories)
  icons/                  UI icon set (heart, star, arrows, search, sound, …) + Home Screen/favicon PNGs — all PNG, no SVG
scripts/
  generate_backgrounds.py     Procedurally generates every illustrated/realistic-style background as SVG
                               (its internal drawing format), merges in the real photos, writes backgrounds.json
  rasterize_backgrounds.py    Converts every generated SVG to JPG in place, deletes the source SVG,
                               and rewrites backgrounds.json to point at the JPGs
  rasterize_icons.py          Converts the UI icon SVGs to transparent PNGs in place, deletes the source SVGs
  import_real_photos.py       Downloads and processes the real flower photos (see below)
  real_photos_picks.json      Hand-reviewed list of which source flower photos to use
  real_photos_manifest.json   Generated metadata for the flower photos (feeds generate_backgrounds.py)
  import_openimages_photos.py     Downloads and processes the Open Images photos (see below)
  openimages_photos_picks.json    Hand-reviewed list of which source photos to use, with titles
  openimages_photos_manifest.json Generated metadata for those photos (feeds generate_backgrounds.py)
```

The shipped image set (everything under `images/`) is **JPG/PNG only — no
SVG files are committed to the repo.**

## About the artwork

Most backgrounds are **original, procedurally-generated artwork** — built
from simple vector shapes (gradients, circles, stars, hearts, flowers,
animal faces, etc.) composed by `scripts/generate_backgrounds.py`. Nothing
is sourced from outside the repo, so there are no licensing concerns.

Internally, `generate_backgrounds.py` still draws each piece as SVG (it's a
convenient vector format to compose shapes in), but that's strictly a build
detail — a second step, `scripts/rasterize_backgrounds.py`, renders every
SVG to a JPG via headless Chromium and deletes the SVG, so the files actually
shipped in `images/backgrounds/` and referenced by the app are all JPG.

To regenerate or extend the set (e.g. add more variants per category):

```
python3 scripts/generate_backgrounds.py     # (re)generates the art as SVG
python3 scripts/rasterize_backgrounds.py    # converts SVG -> JPG, updates backgrounds.json
```

Re-running is deterministic (each variant is seeded). The first script
overwrites `images/backgrounds/**/*.svg` and `images/backgrounds.json` in
place (and re-merges the real photo metadata, see below, if present); the
second script then converts those SVGs to JPG and removes them, leaving no
SVG files behind.

UI icons (heart, search, arrows, etc.) follow the same pattern: they're
hand-authored as SVG for easy editing, then `scripts/rasterize_icons.py`
renders them to transparent PNGs and deletes the SVG sources. If you edit an
icon, re-run:

```
python3 scripts/rasterize_icons.py
```

### Real photos

354 of the backgrounds are `style: "photo"` — genuine photographs rather
than generated artwork, all of them Flickr originals under **Creative
Commons Attribution 2.0 (CC BY 2.0)**, each carrying its photographer and
source URL in the `credit` field that the preview view displays. They come
from two separate imports, described below, and share the same shape: a
hand-reviewed picks file pins the exact source images, an importer writes
the cropped JPGs plus a metadata manifest, and `generate_backgrounds.py`
merges every manifest it finds into `backgrounds.json`.

#### Flowers & Florals (40 photos)

These 40 photographs — both landscape
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

#### Open Images (314 photos, 22 categories)

`scripts/import_openimages_photos.py` pulls the rest from Google's
[Open Images Dataset](https://storage.googleapis.com/openimages/web/index.html)
— ~9M Flickr photographs, every one of them **CC BY 2.0**, with the
photographer and the original Flickr page recorded in the dataset's own
image-metadata CSVs. Metadata comes from `storage.googleapis.com`; the images
themselves come from the CVDF-hosted mirror on `s3.amazonaws.com`, resized to
1024px on the long edge.

| Category | Photos | | Category | Photos |
|---|--:|---|---|--:|
| Dogs & Puppies | 59 | | Butterflies & Insects | 11 |
| Flowers & Florals | 20 | | Winter & Holiday | 11 |
| Cats & Kittens | 17 | | Food & Treats | 10 |
| Horses & Ponies | 15 | | Arctic & Polar Animals | 10 |
| Cute Animals | 15 | | Weather | 9 |
| Birds & Feathers | 15 | | Space & Planets | 9 |
| Ocean & Sea Life | 15 | | Circus & Carnival | 9 |
| Summer & Beach | 15 | | Spring & Garden | 8 |
| Nature Scenes | 15 | | Huskies | 7 |
| Autumn & Fall | 13 | | Tea Party | 7 |
| Safari & Desert | 12 | | | |
| Koalas & Kangaroos | 12 | | | |

Candidates were harvested from the validation + test subsets by
cross-referencing Open Images' human-verified image labels (Kitten, Rose,
Butterfly, Rainbow, Penguin, Jellyfish, …) with its bounding boxes, then
filtered down to things that stand a chance as a wallpaper: the photo must be
CC BY 2.0; it must carry no `Person` / `Human face` / `Text` / `Poster` /
`Car` label, which removes both strangers' faces and most
signage-and-clutter shots; and where the subject is one of the 600 boxable
classes, its box must cover at least 10% of the frame so the subject is
actually the subject. Dogs are the exception — Open Images has no "puppy"
class, so that pool was every image with a `Dog` box whose original Flickr
*title* mentions a puppy.

Everything surviving those filters (~900 images) was downloaded, laid out on
contact sheets and reviewed by eye; roughly a third was kept. The rest went
for the usual dataset reasons — watermarks, date stamps and caption overlays,
photo collages, product and museum shots, craft/plush/CGI stand-ins for the
real animal, brand logos, nursing or newborn litters, blurry or very dark
frames, and shots where a person rather than the subject dominates.
`scripts/openimages_photos_picks.json` pins the reviewed selection (image id,
subset, target category, subject and a hand-written title per photo), so
re-running the import is reproducible — it never re-rolls the selection.

Each photo is cover-cropped to whichever iPad orientation matches the source
— landscape 2732×2048 or portrait 2048×2732 — so a landscape photo is never
cropped down to a portrait sliver, and gets a light unsharp pass to offset
the upscale from the 1024px source.

To re-run the import (downloads ~60MB of metadata CSVs plus the source JPGs
into a gitignored `.cache/`, so a second run is nearly instant):

```
pip install Pillow
python3 scripts/import_openimages_photos.py
python3 scripts/generate_backgrounds.py
```

Adding another category is a two-step job: add its slug to `CATEGORIES` in
the importer (display name + bonus search tags, mirroring
`generate_backgrounds.py`), then add picks naming that slug. Widening the set
further is mostly a matter of pointing the same filter at Open Images'
**train** subset — ~1.7M more images in the same CSV format under the same
license — which was skipped here only because its metadata CSV is ~2GB.

#### Other sources

The categories still without real photos are the make-believe ones —
unicorns, mermaids, fairies, princesses, dragons, superheroes, robots — plus
a few (Ballet & Dance, Fashion & Shopping, School & Learning) where every
usable Open Images photo has a stranger's face in it, which the person
filter deliberately drops. Those stay illustrated-only on purpose.

What's reachable is the real constraint on everything else: this build
environment's egress policy allows `storage.googleapis.com`,
`s3.amazonaws.com` and `github.com`/`raw.githubusercontent.com`, and every
other real-photo host tested (Wikimedia Commons, Unsplash, Pexels, Pixabay,
Openverse, Flickr, `thor.robots.ox.ac.uk`) is blocked. Datasets that are
reachable but *not* usable were also checked and rejected: Stanford Dogs and
the Kaggle Cats & Dogs subset both carry research-only terms rather than a
redistribution licence, and the Oxford-IIIT Pet dataset (CC BY-SA 4.0) is
hosted on a blocked domain. That leaves Open Images as the practical source,
and it is nowhere near exhausted — its label vocabulary covers plenty this
app hasn't tapped yet (reptiles, farm animals, jungle, sports, musical
instruments, castles).

## Setting the real wallpaper

No browser API can set a device's actual wallpaper directly, so "Set as
Background" does the next best thing: it triggers iOS's native share sheet
(via the Web Share API) with the full-resolution image attached, so a tap
away is "Save Image" to Photos, then Photos' own Share → Use as Wallpaper
flow sets it for real. On browsers/devices without file-sharing support it
falls back to a plain download instead. Either way a toast under the button
explains the next tap.
