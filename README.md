# Backdrop Buddies 🌈

A fun, colorful web app that lets kids browse and pick from **150 original
iPad backgrounds** across 25 categories — rainbows, unicorns, dinosaurs,
mermaids, space, sports, and more.

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
- Search box + horizontally-scrolling category tabs (including a Favorites tab)
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
  backgrounds.json        Metadata for every background (id, title, category, tags…)
  backgrounds/<category>/ 150 original SVG background artworks, 6 per category
  icons/                  UI icon set (heart, star, arrows, search, sound, …)
scripts/
  generate_backgrounds.py Procedurally generates every background SVG + the
                           backgrounds.json metadata file
```

## About the artwork

Every background is an **original, procedurally-generated SVG** — built from
simple vector shapes (gradients, circles, stars, hearts, flowers, animal
faces, etc.) composed by `scripts/generate_backgrounds.py`. Nothing is
sourced from outside the repo, so there are no licensing concerns, and since
they're vector graphics they stay crisp at any iPad resolution.

To regenerate or extend the set (e.g. add more variants per category):

```
python3 scripts/generate_backgrounds.py
```

Re-running is deterministic (each variant is seeded), and it overwrites
`images/backgrounds/**/*.svg` and `images/backgrounds.json` in place.
