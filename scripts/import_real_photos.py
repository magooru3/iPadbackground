#!/usr/bin/env python3
"""
Imports a curated set of REAL photographs into images/backgrounds/, sourced
from the TensorFlow "flower_photos" dataset -- ~3,670 flower photos scraped
from Flickr, distributed under Creative Commons Attribution 2.0 (CC BY 2.0),
with every photo's original photographer and Flickr URL documented in the
dataset's own LICENSE.txt.

  Dataset:  https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz
  License:  https://creativecommons.org/licenses/by/2.0/

The dataset is known to contain a handful of mislabeled/noisy entries (a
handful of images across daisy/dandelion/roses/sunflowers/tulips are not
actually pictures of that flower, or aren't appropriate for a kids' app --
one is even a picture of a dog). `real_photos_picks.json` is a hand-reviewed
list of specific source files that were checked against a contact sheet
before being selected, so re-running this script is safe and reproducible
-- it does not re-roll the selection.

Output: JPEGs in images/backgrounds/flowers-florals/photos/ (both landscape
2732x2048 and portrait 2048x2732, cover-cropped from the source) plus
scripts/real_photos_manifest.json, which generate_backgrounds.py merges
into images/backgrounds.json (style: "photo") on its next run.

Usage:
    python3 scripts/import_real_photos.py
"""
import io
import json
import os
import re
import tarfile
import urllib.request

from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_URL = "https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz"
PICKS_PATH = os.path.join(ROOT, "scripts", "real_photos_picks.json")
MANIFEST_PATH = os.path.join(ROOT, "scripts", "real_photos_manifest.json")
OUT_DIR = os.path.join(ROOT, "images", "backgrounds", "flowers-florals", "photos")

LANDSCAPE = (2732, 2048)
PORTRAIT = (2048, 2732)
TITLE_WORDS = {"daisy": "Daisy", "dandelion": "Dandelion", "roses": "Rose",
               "sunflowers": "Sunflower", "tulips": "Tulip"}
MOODS = ["Garden", "Wild", "Sunlit", "Close-Up", "Field of", "Blooming", "Golden", "Morning"]


def parse_license(tar):
    m = {}
    f = tar.extractfile("flower_photos/LICENSE.txt")
    for raw in f.read().decode("utf-8").splitlines():
        mm = re.match(r"^(\S+\.jpg)\s+CC-BY by (.+?) - (https?://\S+)$", raw.strip())
        if mm:
            path, author, url = mm.groups()
            m[path] = {"author": author, "url": url}
    return m


def cover_crop(im, target_w, target_h):
    src_w, src_h = im.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    im2 = im.resize((new_w, new_h), Image.LANCZOS)
    left, top = (new_w - target_w) // 2, (new_h - target_h) // 2
    return im2.crop((left, top, left + target_w, top + target_h))


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    picks = json.load(open(PICKS_PATH))

    print(f"Downloading {DATASET_URL} ...")
    with urllib.request.urlopen(DATASET_URL) as resp:
        data = resp.read()
    print(f"Downloaded {len(data)/1e6:.0f} MB, extracting selected files...")

    manifest = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        license_map = parse_license(tar)
        for cat, files in picks.items():
            label = TITLE_WORDS[cat]
            for i, f in enumerate(files):
                rel = os.path.relpath(f, "flower_photos")
                lic = license_map.get(rel)
                if not lic:
                    print("WARNING: no license entry for", rel, "-- skipping")
                    continue
                orientation = "landscape" if i < 5 else "portrait"
                target = LANDSCAPE if orientation == "landscape" else PORTRAIT

                raw = tar.extractfile(f).read()
                im = Image.open(io.BytesIO(raw))
                im = ImageOps.exif_transpose(im).convert("RGB")
                out_im = cover_crop(im, *target)

                mood = MOODS[i % len(MOODS)]
                title = f"{mood} {label}".strip()
                file_slug = slugify(f"{cat}-{title}-{i}")
                filename = f"{file_slug}.jpg"
                out_im.save(os.path.join(OUT_DIR, filename), "JPEG", quality=85, optimize=True)

                manifest.append({
                    "id": f"flowers-florals/photo-{file_slug}",
                    "title": title,
                    "category": "flowers-florals",
                    "categoryName": "Flowers & Florals",
                    "filename": f"images/backgrounds/flowers-florals/photos/{filename}",
                    "style": "photo",
                    "orientation": orientation,
                    "credit": f'Photo by {lic["author"]} on Flickr, licensed CC BY 2.0 ({lic["url"]})',
                    "tags": list(dict.fromkeys([
                        "flowers florals", "flowers & florals", "photo", "real photo",
                        cat, label.lower(), mood.lower(), orientation, "flower", "garden", "nature",
                    ])),
                })

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {len(manifest)} real photos + {MANIFEST_PATH}")
    print("Run generate_backgrounds.py next to merge them into backgrounds.json.")


if __name__ == "__main__":
    main()
