#!/usr/bin/env python3
"""
Imports a curated set of REAL photographs into images/backgrounds/, sourced
from Google's Open Images Dataset -- ~9M Flickr photos, every one of which is
distributed under Creative Commons Attribution 2.0 (CC BY 2.0), with the
photographer's name and the original Flickr page recorded in the dataset's own
image metadata CSVs.

  Dataset:  https://storage.googleapis.com/openimages/web/index.html
  Images:   https://s3.amazonaws.com/open-images-dataset/<subset>/<id>.jpg
            (the CVDF-hosted mirror, resized to 1024px on the long edge)
  License:  https://creativecommons.org/licenses/by/2.0/

This is the same deal as scripts/import_real_photos.py (which pulls flowers
from the TensorFlow flower_photos dataset): genuine photographs, a permissive
license, and per-photo attribution that ships in backgrounds.json. The two
scripts are deliberately separate -- different source datasets, different
metadata formats -- but they produce the same shape of manifest and both get
merged by generate_backgrounds.py.

How the picks were made (and why they're pinned):

  Candidates were harvested from the validation + test subsets by
  cross-referencing Open Images' human-verified image labels (Kitten, Rose,
  Butterfly, Rainbow, Penguin, Jellyfish, ...) with its bounding boxes, then
  filtered down to things that stand a chance as a wallpaper:

    - the photo must be CC BY 2.0 (all of Open Images is, but it's asserted
      per-photo rather than assumed);
    - no Person / Human face / Text / Poster / Car label, which removes both
      strangers' faces and most signage-and-clutter shots;
    - where the subject is one of the 600 boxable classes, its box must cover
      at least 10% of the frame, so the subject is actually the subject.

  Dogs are the one class handled differently: Open Images has no "puppy"
  class, so that pool was every image with a Dog box whose original Flickr
  *title* mentions a puppy.

  Everything surviving those filters was downloaded, laid out on contact
  sheets and reviewed by eye. Roughly a third was kept. The rest went for the
  usual dataset reasons: watermarks, date stamps and caption overlays, photo
  collages, product and museum shots, craft/plush/CGI stand-ins for the real
  animal, brand logos, nursing or newborn litters, blurry or very dark frames,
  and shots where a person rather than the subject dominates.

  scripts/openimages_photos_picks.json is that hand-reviewed list -- image id,
  subset, target category, subject and a hand-written title per photo -- so
  re-running this script is safe and reproducible: it does not re-roll the
  selection. To widen the pool later, the same filter can be pointed at Open
  Images' *train* subset (~1.7M more images, same CSV format, same license);
  it was skipped here only because its metadata CSV is ~2GB.

Output: JPEGs in images/backgrounds/<category>/photos/ (2732x2048 landscape or
2048x2732 portrait, whichever crops the source least) plus
scripts/openimages_photos_manifest.json, which generate_backgrounds.py merges
into images/backgrounds.json (style: "photo") on its next run.

Usage:
    pip install Pillow
    python3 scripts/import_openimages_photos.py
"""
import collections
import csv
import html
import json
import os
import re
import sys
import urllib.request

from PIL import Image, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICKS_PATH = os.path.join(ROOT, "scripts", "openimages_photos_picks.json")
MANIFEST_PATH = os.path.join(ROOT, "scripts", "openimages_photos_manifest.json")
CACHE_DIR = os.path.join(ROOT, ".cache", "open-images")

# Per-image metadata: ImageID, Author, OriginalLandingURL, License, Rotation.
METADATA_URL = ("https://storage.googleapis.com/openimages/2018_04/"
                "{subset}/{subset}-images-with-rotation.csv")
IMAGE_URL = "https://s3.amazonaws.com/open-images-dataset/{subset}/{image_id}.jpg"
CC_BY_2 = "https://creativecommons.org/licenses/by/2.0/"

LANDSCAPE = (2732, 2048)
PORTRAIT = (2048, 2732)

# Target categories: slug -> (display name, bonus search tags). These mirror
# CATS / CATEGORY_TAGS in generate_backgrounds.py; a pick naming a category
# that isn't listed here is an error rather than a silent default.
CATEGORIES = {
    "dogs-puppies": ("Dogs & Puppies", ["dog", "dogs", "puppy", "puppies", "pet", "breed"]),
    "huskies": ("Huskies", ["dog", "dogs", "puppy", "husky", "pet", "sled dog", "winter dog"]),
    "cats-kittens": ("Cats & Kittens", ["cat", "kitten", "pet", "feline"]),
    "flowers-florals": ("Flowers & Florals", ["flower", "floral", "garden", "bloom", "botanical"]),
    "butterflies-insects": ("Butterflies & Insects", ["butterfly", "insect", "bug", "garden", "wings"]),
    "horses-ponies": ("Horses & Ponies", ["horse", "pony", "ponies", "equestrian", "stable", "riding"]),
    "cute-animals": ("Cute Animals", ["animal", "animals", "pet", "cute", "baby animal"]),
    "birds-feathers": ("Birds & Feathers", ["bird", "feather", "wings", "tropical bird", "flying"]),
    "ocean-sea-life": ("Ocean & Sea Life", ["ocean", "sea", "marine", "underwater", "aquatic", "fish"]),
    "summer-beach": ("Summer & Beach", ["summer", "beach", "sun", "vacation", "tropical"]),
    "food-treats": ("Food & Treats", ["food", "treat", "snack", "sweet", "dessert"]),
    "nature-scenes": ("Nature Scenes", ["nature", "outdoors", "scenery", "landscape"]),
    "winter-holiday": ("Winter & Holiday", ["winter", "holiday", "christmas", "snow", "festive"]),
    "autumn-fall": ("Autumn & Fall", ["autumn", "fall", "leaves", "pumpkin", "harvest", "cozy"]),
    "spring-garden": ("Spring & Garden", ["spring", "garden", "gardening", "flowers", "bloom", "bees"]),
    "weather": ("Weather", ["weather", "sky", "clouds", "rain", "climate"]),
    "safari-desert": ("Safari & Desert", ["safari", "desert", "wild animal", "savanna", "jungle animal"]),
    "arctic-polar": ("Arctic & Polar Animals", ["arctic", "polar", "cold", "snow", "ice", "winter animal"]),
    "koalas-kangaroos": ("Koalas & Kangaroos", ["koala", "kangaroo", "australia", "australian animal", "marsupial"]),
    "space-planets": ("Space & Planets", ["space", "galaxy", "stars", "astronomy", "cosmic"]),
    "tea-party": ("Tea Party", ["tea party", "teacup", "teapot", "cookies", "fancy", "whimsical"]),
    "circus-carnival": ("Circus & Carnival", ["circus", "carnival", "fair", "fun", "festival"]),
}
# Words not worth pulling out of a title as a search tag.
STOPWORDS = {"a", "an", "and", "at", "from", "in", "of", "on", "over", "the",
             "with", "one", "two", "three", "up", "under", "above", "along",
             "says", "held", "close", "big", "little", "her", "s"}


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
        category, title, subject = pick["category"], pick["title"], pick["subject"]
        if category not in CATEGORIES:
            raise SystemExit(f"{image_id}: unknown category {category!r} -- add it to CATEGORIES")
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
        category_name, bonus_tags = CATEGORIES[category]
        # Same tag recipe generate_backgrounds.py uses for the generated art:
        # category slug words, category name, style, category bonus tags, then
        # keywords from the title -- plus the pick's subject and orientation.
        tags = ([category.replace("-", " "), category_name.lower(), "photo",
                 "real photo", orientation] + bonus_tags
                + [subject.lower()] + title_tags(title))
        manifest.append({
            "id": f"{category}/photo-{file_slug}",
            "title": title,
            "category": category,
            "categoryName": category_name,
            "filename": f"images/backgrounds/{category}/photos/{filename}",
            "style": "photo",
            "orientation": orientation,
            "credit": (f"Photo by {author} on Flickr, licensed CC BY 2.0 "
                       f"({info['landing_url']})"),
            "tags": list(dict.fromkeys(tags)),
        })

    if not manifest:
        print("No photos imported -- nothing written.")
        return 1

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    by_cat = collections.Counter(e["category"] for e in manifest)
    print(f"Wrote {len(manifest)} real photos + {MANIFEST_PATH}")
    for slug, n in sorted(by_cat.items()):
        print(f"  {slug:22s} {n}")
    print("Run generate_backgrounds.py next to merge them into backgrounds.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
