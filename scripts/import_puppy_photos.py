#!/usr/bin/env python3
"""
Imports a curated set of REAL puppy photographs into images/backgrounds/,
sourced from Google's Open Images Dataset -- ~9M Flickr photos, every one of
which is distributed under Creative Commons Attribution 2.0 (CC BY 2.0), with
the photographer's name and the original Flickr page recorded in the dataset's
own image metadata CSVs.

  Dataset:  https://storage.googleapis.com/openimages/web/index.html
  Images:   https://s3.amazonaws.com/open-images-dataset/<subset>/<id>.jpg
            (the CVDF-hosted mirror, resized to 1024px on the long edge)
  License:  https://creativecommons.org/licenses/by/2.0/

This is the same deal as scripts/import_real_photos.py (which pulls flowers
from the TensorFlow flower_photos dataset): genuine photographs, a permissive
license, and per-photo attribution that ships in backgrounds.json. The two
scripts are deliberately separate -- different source datasets, different
metadata formats, different target categories -- but they produce the same
shape of manifest and both get merged by generate_backgrounds.py.

How the picks were made (and why they're pinned):

  Open Images labels dogs (`/m/0bt9lr`) but has no "puppy" class, so the
  candidate pool was built by taking every validation/test image with a Dog
  bounding box whose original Flickr *title* mentions a puppy -- 181 images.
  Those were downloaded, laid out on contact sheets and reviewed by eye, and
  the 66 that actually work as a kid's wallpaper were kept. The rest were
  dropped for the usual dataset reasons: watermarks and date stamps, photo
  collages, nursing/newborn litters, a ceramic dog figurine, a couple of
  genuinely grim titles, blurry or very dark frames, and shots where a person
  rather than the puppy is the subject.

  scripts/puppy_photos_picks.json is that hand-reviewed list, so re-running
  this script is safe and reproducible -- it does not re-roll the selection.
  To widen the pool later, the same filter can be pointed at Open Images'
  *train* subset (~1.7M more images, same CSV format, same license); it was
  skipped here only because its metadata CSV is ~2GB.

Output: JPEGs in images/backgrounds/<category>/photos/ (2732x2048 landscape or
2048x2732 portrait, whichever crops the source least) plus
scripts/puppy_photos_manifest.json, which generate_backgrounds.py merges into
images/backgrounds.json (style: "photo") on its next run.

Usage:
    pip install Pillow
    python3 scripts/import_puppy_photos.py
"""
import csv
import html
import json
import os
import re
import sys
import urllib.request

from PIL import Image, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICKS_PATH = os.path.join(ROOT, "scripts", "puppy_photos_picks.json")
MANIFEST_PATH = os.path.join(ROOT, "scripts", "puppy_photos_manifest.json")
CACHE_DIR = os.path.join(ROOT, ".cache", "open-images")

# Per-image metadata: ImageID, Author, OriginalLandingURL, License, Rotation.
METADATA_URL = ("https://storage.googleapis.com/openimages/2018_04/"
                "{subset}/{subset}-images-with-rotation.csv")
IMAGE_URL = "https://s3.amazonaws.com/open-images-dataset/{subset}/{image_id}.jpg"
CC_BY_2 = "https://creativecommons.org/licenses/by/2.0/"

LANDSCAPE = (2732, 2048)
PORTRAIT = (2048, 2732)

CATEGORY_NAMES = {"dogs-puppies": "Dogs & Puppies", "huskies": "Huskies"}
CATEGORY_TAGS = {
    "dogs-puppies": ["dogs puppies", "dogs & puppies", "dog", "dogs", "puppy",
                     "puppies", "pet", "breed"],
    "huskies": ["huskies", "husky", "dog", "dogs", "puppy", "puppies", "pet",
                "sled dog"],
}
# Words worth pulling out of a title so search finds a breed by name.
STOPWORDS = {"a", "an", "and", "in", "of", "on", "the", "two", "three", "up",
             "says", "held", "close", "big", "little"}


def cached_download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"Downloading {url} ...")
    with urllib.request.urlopen(url, timeout=600) as resp, open(path, "wb") as f:
        f.write(resp.read())
    return path


def load_metadata(subsets):
    """ImageID -> {author, landing_url, license, rotation} for the given subsets."""
    meta = {}
    for subset in sorted(subsets):
        path = cached_download(METADATA_URL.format(subset=subset),
                               os.path.join(CACHE_DIR, f"{subset}-images.csv"))
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                meta[row["ImageID"]] = {
                    "author": row["Author"],
                    "landing_url": row["OriginalLandingURL"],
                    "license": row["License"],
                    "rotation": row["Rotation"],
                }
    return meta


def cover_crop(im, target_w, target_h):
    src_w, src_h = im.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    im2 = im.resize((new_w, new_h), Image.LANCZOS)
    left, top = (new_w - target_w) // 2, (new_h - target_h) // 2
    return im2.crop((left, top, left + target_w, top + target_h))


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def unescape_author(name):
    """Open Images stores Flickr display names HTML-escaped (e.g. `O&#x27;Brien`)."""
    return html.unescape(name).strip()


def title_tags(title):
    return [w for w in slugify(title).split("-") if w and w not in STOPWORDS]


def main():
    picks = json.load(open(PICKS_PATH))
    meta = load_metadata({p["subset"] for p in picks})

    manifest = []
    for pick in picks:
        image_id, subset = pick["image_id"], pick["subset"]
        category, title = pick["category"], pick["title"]
        info = meta.get(image_id)
        if not info:
            print(f"WARNING: {image_id} not in {subset} metadata -- skipping")
            continue
        if info["license"] != CC_BY_2:
            print(f"WARNING: {image_id} is {info['license']}, not CC BY 2.0 -- skipping")
            continue

        raw = cached_download(IMAGE_URL.format(subset=subset, image_id=image_id),
                              os.path.join(CACHE_DIR, subset, f"{image_id}.jpg"))
        im = ImageOps.exif_transpose(Image.open(raw)).convert("RGB")
        # A few Open Images entries carry an explicit clockwise rotation that
        # is not in the EXIF of the resized copy.
        if info["rotation"] not in ("", "0.0"):
            im = im.rotate(-float(info["rotation"]), expand=True)

        # Pick the orientation the source already is, so a landscape photo is
        # never cropped down to a portrait sliver (and vice versa).
        orientation = "landscape" if im.width >= im.height else "portrait"
        out_im = cover_crop(im, *(LANDSCAPE if orientation == "landscape" else PORTRAIT))
        # Sources top out at 1024px on the long edge, so the frame is always an
        # upscale; a light unsharp pass keeps it from looking mushy on retina.
        out_im = out_im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=3))

        out_dir = os.path.join(ROOT, "images", "backgrounds", category, "photos")
        os.makedirs(out_dir, exist_ok=True)
        file_slug = slugify(f"{title}-{image_id[:6]}")
        filename = f"{file_slug}.jpg"
        out_im.save(os.path.join(out_dir, filename), "JPEG", quality=85, optimize=True)

        author = unescape_author(info["author"])
        manifest.append({
            "id": f"{category}/photo-{file_slug}",
            "title": title,
            "category": category,
            "categoryName": CATEGORY_NAMES[category],
            "filename": f"images/backgrounds/{category}/photos/{filename}",
            "style": "photo",
            "orientation": orientation,
            "credit": (f"Photo by {author} on Flickr, licensed CC BY 2.0 "
                       f"({info['landing_url']})"),
            "tags": list(dict.fromkeys(
                CATEGORY_TAGS[category] + ["photo", "real photo", orientation,
                                           "animal", "cute"] + title_tags(title))),
        })

    if not manifest:
        print("No photos imported -- nothing written.")
        return 1

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {len(manifest)} real puppy photos + {MANIFEST_PATH}")
    print("Run generate_backgrounds.py next to merge them into backgrounds.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
