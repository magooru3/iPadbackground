#!/usr/bin/env python3
"""
Converts every SVG background produced by generate_backgrounds.py into a
JPG, in place, and rewrites images/backgrounds.json to point at the JPGs.
The source .svg files are deleted once their JPG has been written -- the
shipped image set is JPG/PNG only, no SVG.

This is a separate build step (not folded into generate_backgrounds.py)
so the two concerns stay independent: generate_backgrounds.py is the art
generator (edit shapes/palettes there, it still emits SVG internally as
its drawing format), this script is the export/packaging step.

Usage:
    python3 scripts/generate_backgrounds.py   # (re)generates the .svg art
    python3 scripts/rasterize_backgrounds.py  # converts .svg -> .jpg, updates the manifest

Requires Playwright with a Chromium build available (already used
elsewhere in this project's tooling/tests).
"""
import asyncio
import json
import os
import time

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, "images", "backgrounds.json")
JPEG_QUALITY = 85


async def main():
    with open(JSON_PATH) as f:
        data = json.load(f)

    svg_entries = [b for b in data["backgrounds"] if b["filename"].lower().endswith(".svg")]
    print(f"{len(svg_entries)} SVG backgrounds to convert "
          f"({len(data['backgrounds']) - len(svg_entries)} already JPG/PNG).")

    t0 = time.time()
    async with async_playwright() as p:
        launch_kwargs = {}
        pw_chromium = "/opt/pw-browsers/chromium"
        if os.path.exists(pw_chromium):
            launch_kwargs["executable_path"] = pw_chromium
        browser = await p.chromium.launch(**launch_kwargs)
        page = await browser.new_page(device_scale_factor=1)
        current_size = None

        for i, entry in enumerate(svg_entries, start=1):
            svg_path = os.path.join(ROOT, entry["filename"])
            with open(svg_path, encoding="utf-8") as f:
                svg_text = f.read()

            # All our generated SVGs share one of two fixed canvases.
            size = (2732, 2048) if 'viewBox="0 0 2732 2048"' in svg_text else (2048, 2732)
            if size != current_size:
                await page.set_viewport_size({"width": size[0], "height": size[1]})
                current_size = size

            html = (f"<!DOCTYPE html><html><head><style>html,body{{margin:0;padding:0}}"
                    f"svg{{display:block;width:{size[0]}px;height:{size[1]}px}}</style></head>"
                    f"<body>{svg_text}</body></html>")
            await page.set_content(html)

            jpg_path = svg_path[:-4] + ".jpg"
            await page.screenshot(path=jpg_path, type="jpeg", quality=JPEG_QUALITY)
            os.remove(svg_path)

            entry["filename"] = entry["filename"][:-4] + ".jpg"

            if i % 100 == 0 or i == len(svg_entries):
                elapsed = time.time() - t0
                print(f"  {i}/{len(svg_entries)} converted ({elapsed:.0f}s elapsed)")

        await browser.close()

    with open(JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)

    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s. backgrounds.json updated -- all filenames now .jpg/.png.")


if __name__ == "__main__":
    asyncio.run(main())
