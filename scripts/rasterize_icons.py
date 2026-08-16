#!/usr/bin/env python3
"""
Converts every UI icon SVG in images/icons/ into a transparent PNG, in
place, then deletes the source .svg. Unlike rasterize_backgrounds.py
(full-bleed opaque JPGs), these are small UI glyphs that need a
transparent background so they keep working inside colored buttons/pills.

Icons drawn with stroke="currentColor"/fill="currentColor" are rendered
standalone (same as the live app already does via <img src="...svg">),
which resolves currentColor to black -- so the exported PNGs reproduce
the exact look already on screen. Icons with explicit colors (e.g.
heart-filled.svg's #ff6fa5) are unaffected.

Usage:
    python3 scripts/rasterize_icons.py

Requires Playwright with a Chromium build available.
"""
import asyncio
import os

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS_DIR = os.path.join(ROOT, "images", "icons")
EXPORT_SIZE = 128  # px, square -- ample headroom over the largest 24px CSS display size

# app-icon.svg is the Home Screen icon design source; it already has PNG
# derivatives (apple-touch-icon.png, icon-192.png, icon-512.png,
# favicon-32/16.png) rendered in an earlier turn, so it's deleted rather
# than re-rasterized here.
SKIP = {"app-icon.svg"}


async def main():
    svg_files = sorted(
        f for f in os.listdir(ICONS_DIR)
        if f.lower().endswith(".svg") and f not in SKIP
    )
    print(f"{len(svg_files)} icon SVGs to convert.")

    async with async_playwright() as p:
        launch_kwargs = {}
        pw_chromium = "/opt/pw-browsers/chromium"
        if os.path.exists(pw_chromium):
            launch_kwargs["executable_path"] = pw_chromium
        browser = await p.chromium.launch(**launch_kwargs)
        page = await browser.new_page(
            viewport={"width": EXPORT_SIZE, "height": EXPORT_SIZE},
            device_scale_factor=1,
        )

        for name in svg_files:
            svg_path = os.path.join(ICONS_DIR, name)
            with open(svg_path, encoding="utf-8") as f:
                svg_text = f.read()

            html = (
                f"<!DOCTYPE html><html><head><style>"
                f"html,body{{margin:0;padding:0;background:transparent}}"
                f"svg{{display:block;width:{EXPORT_SIZE}px;height:{EXPORT_SIZE}px}}"
                f"</style></head><body>{svg_text}</body></html>"
            )
            await page.set_content(html)

            png_path = svg_path[:-4] + ".png"
            await page.screenshot(path=png_path, type="png", omit_background=True)
            os.remove(svg_path)
            print(f"  {name} -> {os.path.basename(png_path)}")

        await browser.close()

    # Also drop the app-icon.svg design source -- fully replaced by its
    # PNG derivatives, and the project ships no SVGs at all.
    app_icon_svg = os.path.join(ICONS_DIR, "app-icon.svg")
    if os.path.exists(app_icon_svg):
        os.remove(app_icon_svg)
        print("  removed app-icon.svg (PNG derivatives already exist)")

    print("Done. All icons are now PNG.")


if __name__ == "__main__":
    asyncio.run(main())
