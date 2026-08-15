#!/usr/bin/env python3
"""
Generates 100% original, procedurally-drawn SVG background artwork for the
Kids iPad Background Selector app, plus the images/backgrounds.json metadata
file that the web app reads.

Every image is built from scratch out of basic vector shapes (circles,
polygons, paths) composed by this script -- no external image assets are
used or required, so everything here is safe to ship in the repo.

Run:  python3 scripts/generate_backgrounds.py
"""
import json
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "images", "backgrounds")
JSON_PATH = os.path.join(ROOT, "images", "backgrounds.json")

# iPad Pro 12.9" native resolution. Since the file is an SVG it stays crisp
# at any size -- this viewBox just fixes the aspect ratio / coordinate space.
W, H = 2048, 2732


# --------------------------------------------------------------------------
# Low level SVG helpers
# --------------------------------------------------------------------------

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self):
        self.defs = []
        self.body = []
        self._id = 0

    def uid(self, prefix):
        self._id += 1
        return f"{prefix}{self._id}"

    def add(self, s):
        self.body.append(s)

    def add_def(self, s):
        self.defs.append(s)

    def linear_gradient(self, colors, angle=135):
        gid = self.uid("lg")
        rad = math.radians(angle)
        x1 = 50 - 50 * math.cos(rad)
        y1 = 50 - 50 * math.sin(rad)
        x2 = 50 + 50 * math.cos(rad)
        y2 = 50 + 50 * math.sin(rad)
        stops = "".join(
            f'<stop offset="{i / (len(colors) - 1) * 100:.1f}%" stop-color="{c}"/>'
            for i, c in enumerate(colors)
        )
        self.add_def(
            f'<linearGradient id="{gid}" x1="{x1:.1f}%" y1="{y1:.1f}%" '
            f'x2="{x2:.1f}%" y2="{y2:.1f}%">{stops}</linearGradient>'
        )
        return f"url(#{gid})"

    def radial_gradient(self, colors, cx=50, cy=50, r=75):
        gid = self.uid("rg")
        stops = "".join(
            f'<stop offset="{i / (len(colors) - 1) * 100:.1f}%" stop-color="{c}"/>'
            for i, c in enumerate(colors)
        )
        self.add_def(
            f'<radialGradient id="{gid}" cx="{cx}%" cy="{cy}%" r="{r}%">{stops}</radialGradient>'
        )
        return f"url(#{gid})"

    def render(self):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}">'
            f'<defs>{"".join(self.defs)}</defs>'
            f'{"".join(self.body)}'
            f"</svg>"
        )


def rect(x, y, w, h, fill, rx=0, opacity=1, transform=None):
    t = f' transform="{transform}"' if transform else ""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="{rx}" fill="{fill}" opacity="{opacity:.2f}"{t}/>'
    )


def circle(cx, cy, r, fill, opacity=1):
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" opacity="{opacity:.2f}"/>'


def ellipse(cx, cy, rx, ry, fill, opacity=1, transform=None):
    t = f' transform="{transform}"' if transform else ""
    return (
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
        f'fill="{fill}" opacity="{opacity:.2f}"{t}/>'
    )


def polygon(points, fill, opacity=1, transform=None):
    t = f' transform="{transform}"' if transform else ""
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" opacity="{opacity:.2f}"{t}/>'


def path(d, fill, opacity=1, transform=None, stroke=None, stroke_width=0):
    t = f' transform="{transform}"' if transform else ""
    s = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
    return f'<path d="{d}" fill="{fill}" opacity="{opacity:.2f}"{t}{s}/>'


def line(x1, y1, x2, y2, stroke, width, opacity=1, cap="round"):
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width}" stroke-linecap="{cap}" opacity="{opacity:.2f}"/>'
    )


def group(items, transform=None, opacity=None):
    attrs = ""
    if transform:
        attrs += f' transform="{transform}"'
    if opacity is not None:
        attrs += f' opacity="{opacity:.2f}"'
    return f"<g{attrs}>{''.join(items)}</g>"


def star_points(cx, cy, r_outer, r_inner, points=5, rotation=-90):
    pts = []
    step = 360 / (points * 2)
    for i in range(points * 2):
        r = r_outer if i % 2 == 0 else r_inner
        a = math.radians(rotation + i * step)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def star_shape(cx, cy, r, fill, points=5, rotation=-90, opacity=1):
    return polygon(star_points(cx, cy, r, r * 0.42, points, rotation), fill, opacity)


def sparkle_shape(cx, cy, r, fill, rotation=0, opacity=1):
    # 4-point twinkle sparkle
    pts = star_points(cx, cy, r, r * 0.18, 4, rotation)
    return polygon(pts, fill, opacity)


def heart_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    d = (
        f"M {cx} {cy + 30*s} "
        f"C {cx - 70*s} {cy - 40*s}, {cx - 30*s} {cy - 100*s}, {cx} {cy - 55*s} "
        f"C {cx + 30*s} {cy - 100*s}, {cx + 70*s} {cy - 40*s}, {cx} {cy + 30*s} Z"
    )
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return path(d, fill, opacity, transform=t)


def flower_shape(cx, cy, size, petal_color, center_color, petals=5, opacity=1):
    items = []
    for i in range(petals):
        a = 360 / petals * i
        items.append(ellipse(cx, cy - size * 0.55, size * 0.32, size * 0.55, petal_color, opacity,
                              transform=f"rotate({a} {cx} {cy})"))
    items.append(circle(cx, cy, size * 0.3, center_color, opacity))
    return group(items)


def paw_shape(cx, cy, size, fill, opacity=1, rotation=0):
    items = [ellipse(cx, cy + size * 0.15, size * 0.45, size * 0.38, fill, opacity)]
    toe_positions = [(-0.55, -0.55), (-0.2, -0.85), (0.2, -0.85), (0.55, -0.55)]
    for dx, dy in toe_positions:
        items.append(circle(cx + dx * size, cy + dy * size, size * 0.22, fill, opacity))
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def cloud_shape(cx, cy, size, fill, opacity=1):
    items = [
        ellipse(cx, cy, size * 0.55, size * 0.35, fill, opacity),
        circle(cx - size * 0.4, cy + size * 0.05, size * 0.32, fill, opacity),
        circle(cx - size * 0.05, cy - size * 0.2, size * 0.4, fill, opacity),
        circle(cx + size * 0.4, cy + size * 0.05, size * 0.35, fill, opacity),
        circle(cx + size * 0.75, cy + size * 0.12, size * 0.25, fill, opacity),
    ]
    return group(items)


def moon_shape(cx, cy, r, fill, opacity=1):
    d = (
        f"M {cx} {cy - r} "
        f"A {r} {r} 0 1 0 {cx} {cy + r} "
        f"A {r*0.62} {r*0.62} 0 1 1 {cx} {cy - r} Z"
    )
    return path(d, fill, opacity)


def planet_shape(cx, cy, r, body_color, ring_color, opacity=1):
    items = [
        ellipse(cx, cy, r * 1.7, r * 0.4, "none", 0),  # spacer, kept for symmetry
    ]
    items = [
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{r*1.7:.1f}" ry="{r*0.42:.1f}" '
        f'fill="none" stroke="{ring_color}" stroke-width="{r*0.16:.1f}" opacity="{opacity:.2f}"/>',
        circle(cx, cy, r, body_color, opacity),
    ]
    return group(items)


def rocket_shape(cx, cy, size, body_color, accent_color, window_color, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        path(f"M {cx} {cy-100*s} C {cx+45*s} {cy-40*s}, {cx+40*s} {cy+60*s}, {cx+22*s} {cy+90*s} "
             f"L {cx-22*s} {cy+90*s} C {cx-40*s} {cy+60*s}, {cx-45*s} {cy-40*s}, {cx} {cy-100*s} Z",
             body_color, opacity),
        circle(cx, cy - 10 * s, 22 * s, window_color, opacity),
        polygon([(cx - 22*s, cy+70*s), (cx - 60*s, cy+110*s), (cx - 15*s, cy+95*s)], accent_color, opacity),
        polygon([(cx + 22*s, cy+70*s), (cx + 60*s, cy+110*s), (cx + 15*s, cy+95*s)], accent_color, opacity),
        polygon([(cx - 15*s, cy+90*s), (cx + 15*s, cy+90*s), (cx, cy+130*s)], accent_color, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def crown_shape(cx, cy, size, fill, jewel_color, opacity=1):
    s = size / 100.0
    base_y = cy + 40 * s
    pts = [
        (cx - 70*s, base_y), (cx - 70*s, cy), (cx - 35*s, cy + 25*s),
        (cx - 15*s, cy - 45*s), (cx, cy),
        (cx + 15*s, cy - 45*s), (cx + 35*s, cy + 25*s),
        (cx + 70*s, cy), (cx + 70*s, base_y),
    ]
    items = [polygon(pts, fill, opacity)]
    for dx in (-35, 0, 35):
        items.append(circle(cx + dx * s, cy + 15 * s, 8 * s, jewel_color, opacity))
    return group(items)


def bow_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        path(f"M {cx} {cy} C {cx-90*s} {cy-70*s}, {cx-90*s} {cy+70*s}, {cx} {cy} Z", fill, opacity),
        path(f"M {cx} {cy} C {cx+90*s} {cy-70*s}, {cx+90*s} {cy+70*s}, {cx} {cy} Z", fill, opacity),
        circle(cx, cy, 18 * s, fill, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def cupcake_shape(cx, cy, size, wrap_color, icing_color, cherry_color, opacity=1):
    s = size / 100.0
    items = [
        polygon([(cx-45*s, cy+30*s), (cx+45*s, cy+30*s), (cx+30*s, cy+90*s), (cx-30*s, cy+90*s)], wrap_color, opacity),
        path(f"M {cx-48*s} {cy+30*s} C {cx-55*s} {cy-30*s}, {cx-20*s} {cy-60*s}, {cx} {cy-40*s} "
             f"C {cx+20*s} {cy-60*s}, {cx+55*s} {cy-30*s}, {cx+48*s} {cy+30*s} Z", icing_color, opacity),
        circle(cx, cy - 55 * s, 12 * s, cherry_color, opacity),
    ]
    return group(items)


def ice_cream_shape(cx, cy, size, cone_color, scoop_colors, opacity=1):
    s = size / 100.0
    items = [polygon([(cx-30*s, cy+10*s), (cx+30*s, cy+10*s), (cx, cy+90*s)], cone_color, opacity)]
    for i, c in enumerate(scoop_colors):
        items.append(circle(cx, cy - 10 * s - i * 45 * s, 35 * s, c, opacity))
    return group(items)


def musical_note_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        ellipse(cx, cy + 60 * s, 22 * s, 16 * s, fill, opacity, transform=f"rotate(-20 {cx} {cy+60*s})"),
        rect(cx + 18 * s, cy - 90 * s, 8 * s, 150 * s, fill, opacity=opacity),
        path(f"M {cx+26*s} {cy-90*s} C {cx+70*s} {cy-80*s}, {cx+70*s} {cy-40*s}, {cx+26*s} {cy-45*s} Z", fill, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def snowflake_shape(cx, cy, size, fill, opacity=1):
    items = []
    for i in range(6):
        a = 60 * i
        items.append(line(cx, cy, cx, cy - size, fill, size * 0.09, opacity))
        items.append(f'<g transform="rotate({a} {cx} {cy})">'
                      + line(cx, cy, cx, cy - size, fill, size * 0.09, opacity)
                      + line(cx, cy - size * 0.6, cx - size * 0.22, cy - size * 0.8, fill, size * 0.07, opacity)
                      + line(cx, cy - size * 0.6, cx + size * 0.22, cy - size * 0.8, fill, size * 0.07, opacity)
                      + "</g>")
    return group(items[6:])  # drop the plain duplicate lines, keep decorated arms


def palm_tree_shape(cx, cy, size, trunk_color, leaf_color, opacity=1):
    s = size / 100.0
    items = [
        path(f"M {cx-8*s} {cy+90*s} C {cx-20*s} {cy+20*s}, {cx+10*s} {cy-10*s}, {cx+8*s} {cy-80*s} "
             f"L {cx+18*s} {cy-80*s} C {cx+18*s} {cy-10*s}, {cx+2*s} {cy+20*s}, {cx+10*s} {cy+90*s} Z",
             trunk_color, opacity),
    ]
    for i, a in enumerate([-150, -110, -70, -30, 10]):
        rad = math.radians(a)
        ex = cx + 70 * s * math.cos(rad)
        ey = cy - 80 * s + 40 * s * math.sin(rad)
        items.append(ellipse(ex, ey, 55 * s, 18 * s, leaf_color, opacity,
                              transform=f"rotate({a+90} {ex} {ey})"))
    return group(items)


def lightning_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    pts = [(cx+10*s, cy-100*s), (cx-40*s, cy+10*s), (cx-5*s, cy+10*s),
           (cx-15*s, cy+100*s), (cx+45*s, cy-20*s), (cx+5*s, cy-20*s)]
    return polygon(pts, fill, opacity)


def dino_shape(cx, cy, size, fill, spike_color, opacity=1):
    s = size / 100.0
    items = [
        ellipse(cx, cy + 20 * s, 70 * s, 45 * s, fill, opacity),
        circle(cx + 70 * s, cy - 20 * s, 32 * s, fill, opacity),
        circle(cx + 85 * s, cy - 28 * s, 5 * s, "#222222", opacity),
        path(f"M {cx-60*s} {cy+50*s} C {cx-90*s} {cy+70*s}, {cx-95*s} {cy+110*s}, {cx-80*s} {cy+120*s} "
             f"C {cx-60*s} {cy+90*s}, {cx-50*s} {cy+70*s}, {cx-60*s} {cy+50*s} Z", fill, opacity),
    ]
    for i, dx in enumerate([-20, 5, 30, 55]):
        items.append(polygon([(cx+dx*s, cy-30*s), (cx+(dx+12)*s, cy-55*s), (cx+(dx+24)*s, cy-30*s)],
                              spike_color, opacity))
    for lx in (-30, 0, 30):
        items.append(ellipse(cx + lx * s, cy + 68 * s, 10 * s, 16 * s, fill, opacity))
    return group(items)


def car_shape(cx, cy, size, body_color, wheel_color, opacity=1):
    s = size / 100.0
    items = [
        polygon([(cx-90*s, cy+20*s), (cx-60*s, cy-25*s), (cx+40*s, cy-25*s), (cx+70*s, cy+20*s)],
                body_color, opacity),
        rect(cx - 95 * s, cy + 15 * s, 190 * s, 35 * s, body_color, rx=12 * s, opacity=opacity),
        circle(cx - 55 * s, cy + 55 * s, 22 * s, wheel_color, opacity),
        circle(cx + 45 * s, cy + 55 * s, 22 * s, wheel_color, opacity),
    ]
    return group(items)


def mask_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    d = (f"M {cx-90*s} {cy-10*s} C {cx-90*s} {cy-45*s}, {cx-30*s} {cy-45*s}, {cx} {cy-25*s} "
         f"C {cx+30*s} {cy-45*s}, {cx+90*s} {cy-45*s}, {cx+90*s} {cy-10*s} "
         f"C {cx+60*s} {cy+15*s}, {cx+20*s} {cy-5*s}, {cx} {cy} "
         f"C {cx-20*s} {cy-5*s}, {cx-60*s} {cy+15*s}, {cx-90*s} {cy-10*s} Z")
    return path(d, fill, opacity)


def shell_shape(cx, cy, size, fill, opacity=1):
    items = []
    for i in range(7):
        a = -90 + i * 25
        rad = math.radians(a)
        items.append(polygon(
            [(cx, cy), (cx + size * math.cos(rad - 0.15), cy + size * math.sin(rad - 0.15)),
             (cx + size * math.cos(rad + 0.15), cy + size * math.sin(rad + 0.15))],
            fill, opacity))
    items.append(circle(cx, cy, size * 0.18, fill, opacity))
    return group(items)


def fish_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        ellipse(cx, cy, 55 * s, 32 * s, fill, opacity),
        polygon([(cx-50*s, cy), (cx-85*s, cy-30*s), (cx-85*s, cy+30*s)], fill, opacity),
        circle(cx + 30 * s, cy - 8 * s, 6 * s, "#222222", opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def butterfly_shape(cx, cy, size, fill, accent, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        ellipse(cx - 35 * s, cy - 30 * s, 35 * s, 25 * s, fill, opacity),
        ellipse(cx - 30 * s, cy + 25 * s, 25 * s, 20 * s, fill, opacity),
        ellipse(cx + 35 * s, cy - 30 * s, 35 * s, 25 * s, fill, opacity),
        ellipse(cx + 30 * s, cy + 25 * s, 25 * s, 20 * s, fill, opacity),
        circle(cx - 35 * s, cy - 30 * s, 10 * s, accent, opacity),
        circle(cx + 35 * s, cy - 30 * s, 10 * s, accent, opacity),
        rect(cx - 4 * s, cy - 45 * s, 8 * s, 90 * s, "#3a2a1a", rx=4 * s, opacity=opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def castle_shape(cx, cy, size, fill, roof_color, opacity=1):
    s = size / 100.0
    items = [rect(cx - 90 * s, cy - 20 * s, 180 * s, 110 * s, fill, opacity=opacity)]
    for dx in (-90, -30, 30):
        items.append(rect(cx + dx * s, cy - 90 * s, 60 * s, 90 * s, fill, opacity=opacity))
        items.append(polygon(
            [(cx + dx * s, cy - 90 * s), (cx + (dx + 60) * s, cy - 90 * s), (cx + (dx + 30) * s, cy - 140 * s)],
            roof_color, opacity))
    items.append(rect(cx - 20 * s, cy + 20 * s, 40 * s, 70 * s, "#5b3a29", rx=18 * s, opacity=opacity))
    return group(items)


def wings_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        path(f"M {cx} {cy} C {cx-100*s} {cy-90*s}, {cx-140*s} {cy-10*s}, {cx-40*s} {cy+20*s} "
             f"C {cx-90*s} {cy+40*s}, {cx-70*s} {cy+90*s}, {cx} {cy+10*s} Z", fill, opacity),
        path(f"M {cx} {cy} C {cx+100*s} {cy-90*s}, {cx+140*s} {cy-10*s}, {cx+40*s} {cy+20*s} "
             f"C {cx+90*s} {cy+40*s}, {cx+70*s} {cy+90*s}, {cx} {cy+10*s} Z", fill, opacity),
    ]
    return group(items)


def ribbon_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        polygon([(cx-70*s, cy-15*s), (cx+70*s, cy+15*s), (cx+70*s, cy+35*s), (cx-70*s, cy+5*s)], fill, opacity),
        polygon([(cx-70*s, cy+15*s), (cx+70*s, cy-15*s), (cx+70*s, cy+5*s), (cx-70*s, cy+35*s)], fill, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def animal_face_shape(cx, cy, size, fur_color, ear_color, kind, opacity=1):
    """kind in: puppy, kitten, bunny, fox, panda, unicorn"""
    s = size / 100.0
    items = []
    if kind == "bunny":
        items.append(ellipse(cx - 25 * s, cy - 95 * s, 18 * s, 55 * s, fur_color, opacity))
        items.append(ellipse(cx + 25 * s, cy - 95 * s, 18 * s, 55 * s, fur_color, opacity))
        items.append(ellipse(cx - 25 * s, cy - 95 * s, 9 * s, 38 * s, ear_color, opacity))
        items.append(ellipse(cx + 25 * s, cy - 95 * s, 9 * s, 38 * s, ear_color, opacity))
    elif kind == "fox":
        items.append(polygon([(cx-70*s, cy-40*s), (cx-30*s, cy-40*s), (cx-55*s, cy-95*s)], fur_color, opacity))
        items.append(polygon([(cx+70*s, cy-40*s), (cx+30*s, cy-40*s), (cx+55*s, cy-95*s)], fur_color, opacity))
        items.append(polygon([(cx-58*s, cy-48*s), (cx-40*s, cy-48*s), (cx-52*s, cy-80*s)], ear_color, opacity))
        items.append(polygon([(cx+58*s, cy-48*s), (cx+40*s, cy-48*s), (cx+52*s, cy-80*s)], ear_color, opacity))
    elif kind == "unicorn":
        items.append(circle(cx - 45 * s, cy - 60 * s, 22 * s, fur_color, opacity))
        items.append(circle(cx + 45 * s, cy - 60 * s, 22 * s, fur_color, opacity))
        items.append(polygon([(cx-8*s, cy-70*s), (cx+8*s, cy-70*s), (cx, cy-150*s)], "#f4d35e", opacity))
    elif kind == "panda":
        items.append(circle(cx - 55 * s, cy - 60 * s, 26 * s, "#2b2b2b", opacity))
        items.append(circle(cx + 55 * s, cy - 60 * s, 26 * s, "#2b2b2b", opacity))
    else:  # puppy / kitten
        ear_shape_fn = ellipse if kind == "puppy" else polygon
        if kind == "puppy":
            items.append(ellipse(cx - 55 * s, cy - 40 * s, 20 * s, 40 * s, ear_color, opacity,
                                  transform=f"rotate(-20 {cx-55*s} {cy-40*s})"))
            items.append(ellipse(cx + 55 * s, cy - 40 * s, 20 * s, 40 * s, ear_color, opacity,
                                  transform=f"rotate(20 {cx+55*s} {cy-40*s})"))
        else:
            items.append(polygon([(cx-70*s, cy-50*s), (cx-30*s, cy-50*s), (cx-55*s, cy-95*s)], ear_color, opacity))
            items.append(polygon([(cx+70*s, cy-50*s), (cx+30*s, cy-50*s), (cx+55*s, cy-95*s)], ear_color, opacity))
    # head + face (shared)
    items.append(circle(cx, cy, 65 * s, fur_color, opacity))
    items.append(circle(cx - 25 * s, cy - 10 * s, 8 * s, "#2b2b2b", opacity))
    items.append(circle(cx + 25 * s, cy - 10 * s, 8 * s, "#2b2b2b", opacity))
    items.append(ellipse(cx, cy + 15 * s, 10 * s, 7 * s, "#2b2b2b", opacity))
    if kind == "unicorn":
        for dx, c in zip((-14, 0, 14), ["#ff9fd6", "#a6e3ff", "#ffe3a6"]):
            items.append(ellipse(cx + dx * s, cy - 78 * s, 6 * s, 16 * s, c, opacity,
                                  transform=f"rotate({dx} {cx+dx*s} {cy-78*s})"))
    return group(items)


def cat_face_shape(cx, cy, size, fur_color, opacity=1):
    return animal_face_shape(cx, cy, size, fur_color, fur_color, "kitten", opacity)


def mermaid_tail_shape(cx, cy, size, fill, accent, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        path(f"M {cx} {cy-90*s} C {cx+40*s} {cy-40*s}, {cx+30*s} {cy+40*s}, {cx+55*s} {cy+70*s} "
             f"L {cx+90*s} {cy+120*s} L {cx+20*s} {cy+90*s} "
             f"C {cx+10*s} {cy+60*s}, {cx-10*s} {cy+60*s}, {cx-20*s} {cy+90*s} "
             f"L {cx-90*s} {cy+120*s} L {cx-55*s} {cy+70*s} "
             f"C {cx-30*s} {cy+40*s}, {cx-40*s} {cy-40*s}, {cx} {cy-90*s} Z", fill, opacity),
    ]
    for i in range(4):
        items.append(ellipse(cx - 20 * s + i * 14 * s, cy - 20 * s + i * 20 * s, 10 * s, 5 * s, accent, opacity * 0.7))
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def coral_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = []
    for i, a in enumerate([-70, -35, 0, 35, 70]):
        rad = math.radians(a)
        ex = cx + 20 * s * math.sin(rad)
        ey = cy - size * (0.7 + 0.3 * math.cos(rad))
        items.append(f'<path d="M {cx} {cy} Q {ex} {(cy+ey)/2} {ex} {ey}" stroke="{fill}" '
                      f'stroke-width="{14*s}" fill="none" stroke-linecap="round" opacity="{opacity:.2f}"/>')
    return group(items)


def alien_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        path(f"M {cx-55*s} {cy+30*s} C {cx-70*s} {cy-60*s}, {cx-30*s} {cy-100*s}, {cx} {cy-100*s} "
             f"C {cx+30*s} {cy-100*s}, {cx+70*s} {cy-60*s}, {cx+55*s} {cy+30*s} "
             f"C {cx+40*s} {cy+55*s}, {cx-40*s} {cy+55*s}, {cx-55*s} {cy+30*s} Z", fill, opacity),
        ellipse(cx - 22 * s, cy - 20 * s, 14 * s, 20 * s, "#0b0b1a", opacity),
        ellipse(cx + 22 * s, cy - 20 * s, 14 * s, 20 * s, "#0b0b1a", opacity),
    ]
    return group(items)


def soccer_ball_shape(cx, cy, r, base_color, pent_color, opacity=1):
    items = [circle(cx, cy, r, base_color, opacity)]
    items.append(star_shape(cx, cy, r * 0.4, pent_color, points=5, opacity=opacity))
    for i in range(5):
        a = math.radians(-90 + i * 72)
        px = cx + r * 0.62 * math.cos(a)
        py = cy + r * 0.62 * math.sin(a)
        items.append(star_shape(px, py, r * 0.22, pent_color, points=5, rotation=a * 180 / math.pi, opacity=opacity))
    return group(items)


def basketball_shape(cx, cy, r, fill, line_color, opacity=1):
    items = [circle(cx, cy, r, fill, opacity)]
    items.append(line(cx - r, cy, cx + r, cy, line_color, r * 0.06, opacity))
    items.append(line(cx, cy - r, cx, cy + r, line_color, r * 0.06, opacity))
    items.append(f'<path d="M {cx} {cy-r} A {r} {r} 0 0 1 {cx} {cy+r}" fill="none" '
                 f'stroke="{line_color}" stroke-width="{r*0.06:.1f}" opacity="{opacity:.2f}"/>')
    items.append(f'<path d="M {cx} {cy-r} A {r} {r} 0 0 0 {cx} {cy+r}" fill="none" '
                 f'stroke="{line_color}" stroke-width="{r*0.06:.1f}" opacity="{opacity:.2f}"/>')
    return group(items)


def skateboard_shape(cx, cy, size, deck_color, wheel_color, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        rect(cx - 100 * s, cy - 15 * s, 200 * s, 30 * s, deck_color, rx=15 * s, opacity=opacity),
        circle(cx - 65 * s, cy + 25 * s, 12 * s, wheel_color, opacity),
        circle(cx + 65 * s, cy + 25 * s, 12 * s, wheel_color, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def gift_shape(cx, cy, size, box_color, ribbon_color, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 60 * s, cy - 20 * s, 120 * s, 90 * s, box_color, rx=6 * s, opacity=opacity),
        rect(cx - 60 * s, cy - 45 * s, 120 * s, 30 * s, box_color, rx=6 * s, opacity=opacity),
        rect(cx - 12 * s, cy - 45 * s, 24 * s, 115 * s, ribbon_color, opacity=opacity),
        rect(cx - 60 * s, cy - 8 * s, 120 * s, 24 * s, ribbon_color, opacity=opacity),
        path(f"M {cx} {cy-45*s} C {cx-40*s} {cy-90*s}, {cx-60*s} {cy-40*s}, {cx-12*s} {cy-45*s} Z",
             ribbon_color, opacity),
        path(f"M {cx} {cy-45*s} C {cx+40*s} {cy-90*s}, {cx+60*s} {cy-40*s}, {cx+12*s} {cy-45*s} Z",
             ribbon_color, opacity),
    ]
    return group(items)


def bolt_cloud_shape(cx, cy, size, cloud_color, bolt_color, opacity=1):
    return group([cloud_shape(cx, cy - 20, size, cloud_color, opacity),
                  lightning_shape(cx, cy + 60, size * 0.7, bolt_color, opacity)])


def raindrop_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    d = f"M {cx} {cy-60*s} C {cx+35*s} {cy}, {cx+35*s} {cy+50*s}, {cx} {cy+55*s} C {cx-35*s} {cy+50*s}, {cx-35*s} {cy}, {cx} {cy-60*s} Z"
    return path(d, fill, opacity)


def sandcastle_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [rect(cx - 90 * s, cy, 180 * s, 60 * s, fill, rx=6 * s, opacity=opacity)]
    for dx in (-90, -30, 30):
        items.append(rect(cx + dx * s, cy - 60 * s, 60 * s, 65 * s, fill, opacity=opacity))
        items.append(polygon([(cx+dx*s, cy-60*s), (cx+(dx+60)*s, cy-60*s), (cx+(dx+30)*s, cy-95*s)], fill, opacity))
    items.append(triangle_flag(cx, cy - 95 * s, 24 * s, "#ff5e78", opacity))
    return group(items)


def triangle_flag(cx, cy, size, fill, opacity=1):
    return group([
        line(cx, cy, cx, cy - size * 1.6, "#6b4423", size * 0.12, opacity),
        polygon([(cx, cy - size * 1.6), (cx + size, cy - size * 1.3), (cx, cy - size)], fill, opacity),
    ])


def sun_shape(cx, cy, r, fill, ray_color, opacity=1):
    items = []
    for i in range(12):
        a = math.radians(i * 30)
        x1 = cx + r * 1.15 * math.cos(a)
        y1 = cy + r * 1.15 * math.sin(a)
        x2 = cx + r * 1.55 * math.cos(a)
        y2 = cy + r * 1.55 * math.sin(a)
        items.append(line(x1, y1, x2, y2, ray_color, r * 0.12, opacity))
    items.append(circle(cx, cy, r, fill, opacity))
    return group(items)


def triangle_shape(cx, cy, size, fill, opacity=1, rotation=0):
    pts = [(cx, cy - size), (cx - size * 0.87, cy + size * 0.5), (cx + size * 0.87, cy + size * 0.5)]
    return polygon(pts, fill, opacity, transform=(f"rotate({rotation} {cx} {cy})" if rotation else None))


def wave_stripe(y, amp, color, opacity=1, offset=0):
    pts = "M 0 {y} ".format(y=y)
    segs = 8
    d = f"M -50 {y+amp}"
    for i in range(segs + 1):
        x = -50 + (W + 100) * i / segs
        yy = y + amp * math.sin(offset + i * math.pi / 2)
        d += f" L {x:.0f} {yy:.0f}"
    d += f" L {W+50} {H+50} L -50 {H+50} Z"
    return path(d, color, opacity)


# --------------------------------------------------------------------------
# Scene / scatter helpers
# --------------------------------------------------------------------------

def scatter(svg, rng, motif_fn, count, x_range=(0, W), y_range=(0, H), size_range=(90, 220),
            rotate=False, opacity_range=(0.85, 1.0)):
    for _ in range(count):
        cx = rng.uniform(*x_range)
        cy = rng.uniform(*y_range)
        size = rng.uniform(*size_range)
        rot = rng.uniform(0, 360) if rotate else 0
        op = rng.uniform(*opacity_range)
        svg.add(motif_fn(cx, cy, size, rot, op))


def background_rect(svg, fill):
    svg.add(rect(0, 0, W, H, fill))


# --------------------------------------------------------------------------
# Category definitions
# --------------------------------------------------------------------------
# Each category: slug, name, list of 6 (title, builder_fn) pairs.
# Builder receives (svg, rng) and paints the full scene.

def grad_bg(svg, colors, angle=135):
    background_rect(svg, svg.linear_gradient(colors, angle))


CATS = []


def cat(slug, name, variants):
    CATS.append({"slug": slug, "name": name, "variants": variants})


# ---- 1. Rainbow & Gradients ------------------------------------------------
def rainbow_arcs(svg, rng, colors):
    cx, cy = W / 2, H * 0.85
    r0 = W * 0.75
    band = r0 / len(colors)
    for i, c in enumerate(colors):
        r = r0 - i * band
        svg.add(f'<path d="M {cx-r} {cy} A {r} {r} 0 0 1 {cx+r} {cy}" fill="none" '
                f'stroke="{c}" stroke-width="{band*0.9:.1f}" stroke-linecap="round"/>')


def v_rainbow_pastel(svg, rng):
    grad_bg(svg, ["#ffd6ec", "#d6f0ff", "#e8ffd6"], 120)
    rainbow_arcs(svg, rng, ["#ff9fbf", "#ffd39f", "#fff59f", "#c2f0c2", "#9fd8ff", "#c9a6ff"])
    scatter(svg, rng, lambda cx, cy, s, r, o: circle(cx, cy, s * 0.25, rng.choice(
        ["#ffffff"]), o * 0.6), 18, size_range=(40, 90))

def v_rainbow_bright(svg, rng):
    grad_bg(svg, ["#ff4d6d", "#ff9f1c", "#ffe74c", "#5cd85c", "#3aa6ff", "#8e5cff"], 60)
    scatter(svg, rng, lambda cx, cy, s, r, o: sparkle_shape(cx, cy, s * 0.5, "#ffffff", r, o * 0.9), 24)

def v_sunset(svg, rng):
    grad_bg(svg, ["#3a1c71", "#d76d77", "#ffaf7b"], 90)
    svg.add(circle(W * 0.5, H * 0.62, W * 0.28, "#fff2b2", 0.9))
    for i in range(6):
        y = H * (0.7 + i * 0.05)
        svg.add(rect(0, y, W, 8, "#3a1c71", opacity=0.25))

def v_galaxy(svg, rng):
    grad_bg(svg, ["#0f0c29", "#302b63", "#24243e"], 100)
    for _ in range(140):
        svg.add(circle(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(2, 6), "#ffffff", rng.uniform(0.3, 1)))
    scatter(svg, rng, lambda cx, cy, s, r, o: circle(cx, cy, s * 0.7, rng.choice(
        ["#c9a6ff", "#7fd8ff", "#ff9fd6"]), o * 0.5), 8, size_range=(120, 260))

def v_cotton_candy(svg, rng):
    grad_bg(svg, ["#a1c4fd", "#c2e9fb", "#fbc2eb"], 150)
    scatter(svg, rng, lambda cx, cy, s, r, o: cloud_shape(cx, cy, s, "#ffffff", o * 0.7), 10, size_range=(140, 260))

def v_neon_gradient(svg, rng):
    grad_bg(svg, ["#00f5d4", "#00bbf9", "#9b5de5", "#f15bb5"], 45)
    scatter(svg, rng, lambda cx, cy, s, r, o: star_shape(cx, cy, s * 0.4, "#ffffff", 4, r, o * 0.8), 16)

cat("rainbow-gradients", "Rainbow & Gradients", [
    ("Pastel Rainbow Sky", v_rainbow_pastel),
    ("Bright Rainbow Blast", v_rainbow_bright),
    ("Dreamy Sunset", v_sunset),
    ("Galaxy Swirl", v_galaxy),
    ("Cotton Candy Clouds", v_cotton_candy),
    ("Neon Gradient Glow", v_neon_gradient),
])

# ---- 2. Geometric Patterns --------------------------------------------------
def v_polka_dots(svg, rng):
    grad_bg(svg, ["#ffe3f1", "#ffd1e8"], 90)
    cols = ["#ff6fa5", "#ffd166", "#06d6a0", "#4cc9f0"]
    rows, colsn = 14, 10
    for ry in range(rows):
        for cxn in range(colsn):
            x = (cxn + 0.5) * (W / colsn) + (40 if ry % 2 else -40)
            y = (ry + 0.5) * (H / rows)
            svg.add(circle(x, y, 46, rng.choice(cols), 0.9))

def v_stripes(svg, rng):
    grad_bg(svg, ["#fff3b0", "#ffe066"], 90)
    cols = ["#ff6b6b", "#4ecdc4", "#ffd166", "#1a936f"]
    n = 14
    for i in range(-2, n + 2):
        svg.add(rect(i * (W / (n - 4)), -100, W / (n - 4) * 0.55, H + 200, rng.choice(cols), opacity=0.85,
                     transform=f"skewX(-12)"))

def v_triangles(svg, rng):
    grad_bg(svg, ["#e0f7fa", "#b2ebf2"], 90)
    cols = ["#ff9f1c", "#2ec4b6", "#e71d36", "#ffbf69", "#011627"]
    size = 130
    rows = int(H / (size * 0.87)) + 2
    colsn = int(W / size) + 2
    for r_ in range(rows):
        for c_ in range(colsn):
            x = c_ * size + (size / 2 if r_ % 2 else 0)
            y = r_ * size * 0.87
            rot = 0 if (r_ + c_) % 2 == 0 else 180
            svg.add(triangle_shape(x, y, size * 0.55, rng.choice(cols), 0.9, rot))

def v_stars_pattern(svg, rng):
    grad_bg(svg, ["#1a1a40", "#2d2d6b"], 90)
    cols = ["#ffe66d", "#ff6b6b", "#4ecdc4", "#ffffff", "#c9a6ff"]
    scatter(svg, rng, lambda cx, cy, s, r, o: star_shape(cx, cy, s * 0.4, rng.choice(cols), 5, r, o), 60,
            size_range=(40, 110), rotate=True)

def v_checkerboard(svg, rng):
    grad_bg(svg, ["#fdf6ec", "#fdf6ec"], 0)
    cols = ["#ff8fa3", "#ffd6a5"]
    n = 12
    size = W / n
    for r_ in range(int(H / size) + 1):
        for c_ in range(n):
            if (r_ + c_) % 2 == 0:
                svg.add(rect(c_ * size, r_ * size, size, size, cols[(r_ + c_) // 2 % 2]))

def v_zigzag(svg, rng):
    grad_bg(svg, ["#caf0f8", "#ade8f4"], 90)
    cols = ["#ff6f61", "#ffd166", "#06d6a0", "#4361ee"]
    step = 160
    for i, y in enumerate(range(-step, H + step, step)):
        d = f"M -100 {y}"
        x = -100
        up = True
        while x < W + 100:
            x += step
            d += f" L {x} {y + (step if up else 0)}"
            up = not up
        d += f" L {W+100} {y+step*2} L -100 {y+step*2} Z"
        svg.add(path(d, cols[i % len(cols)], 0.85))

cat("geometric-patterns", "Geometric Patterns", [
    ("Playful Polka Dots", v_polka_dots),
    ("Rainbow Stripes", v_stripes),
    ("Triangle Tumble", v_triangles),
    ("Starry Pattern", v_stars_pattern),
    ("Sweet Checkerboard", v_checkerboard),
    ("Zigzag Party", v_zigzag),
])

# ---- 3. Cute Animals ---------------------------------------------------------
def animal_scene(kind, fur, ear, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        for _ in range(5):
            cx = rng.uniform(150, W - 150)
            cy = rng.uniform(200, H - 200)
            size = rng.uniform(220, 340)
            svg.add(animal_face_shape(cx, cy, size, fur, ear, kind, 0.97))
        scatter(svg, rng, lambda cx, cy, s, r, o: paw_shape(cx, cy, s * 0.3, "#ffffff", o * 0.35, r), 10,
                rotate=True, size_range=(60, 120))
    return build

cat("cute-animals", "Cute Animals", [
    ("Playful Puppies", animal_scene("puppy", "#d9a066", "#8a5a2b", ["#fff2df", "#ffe0b3"])),
    ("Curious Kittens", animal_scene("kitten", "#f2c14e", "#f2c14e", ["#fff8e7", "#ffe9b0"])),
    ("Bouncy Bunnies", animal_scene("bunny", "#ffffff", "#ffc2d1", ["#eaf7ff", "#dff3ff"])),
    ("Sly Little Foxes", animal_scene("fox", "#ff8c42", "#ffffff", ["#fff0e0", "#ffdbb0"])),
    ("Cuddly Pandas", animal_scene("panda", "#ffffff", "#2b2b2b", ["#eafff1", "#d3ffe4"])),
    ("Magical Unicorns", animal_scene("unicorn", "#ffffff", "#ffd6ec", ["#f3e8ff", "#e0c9ff"])),
])

# ---- 4. Nature Scenes --------------------------------------------------------
def v_forest(svg, rng):
    grad_bg(svg, ["#bde0fe", "#a2d6f9"], 90)
    for i, (color, y, s) in enumerate([("#2d6a4f", 0.55, 1), ("#40916c", 0.68, 0.85), ("#52b788", 0.82, 0.7)]):
        for _ in range(9):
            x = rng.uniform(0, W)
            svg.add(triangle_shape(x, H * y, 160 * s, color, 0.95))
            svg.add(triangle_shape(x, H * y - 90 * s, 130 * s, color, 0.95))
    svg.add(circle(W * 0.82, H * 0.15, 90, "#fff4b8", 0.95))

def v_beach(svg, rng):
    grad_bg(svg, ["#a8e6ff", "#e0fbfc"], 90)
    svg.add(sun_shape(W * 0.15, H * 0.15, 100, "#ffe066", "#ffd166"))
    svg.add(rect(0, H * 0.6, W, H * 0.15, "#4cc9f0"))
    svg.add(rect(0, H * 0.7, W, H * 0.4, "#ffe8b0"))
    for _ in range(3):
        svg.add(palm_tree_shape(rng.uniform(150, W - 150), H * rng.uniform(0.55, 0.68), 220, "#8a5a2b", "#2d6a4f"))
    scatter(svg, rng, lambda cx, cy, s, r, o: shell_shape(cx, cy, s * 0.5, "#ffffff", o), 6,
            y_range=(H * 0.75, H * 0.95), size_range=(60, 100))

def v_mountains(svg, rng):
    grad_bg(svg, ["#e0c3fc", "#8ec5fc"], 100)
    for color, y, s in [("#5c6b73", 0.62, 1.1), ("#7d8f96", 0.72, 0.9), ("#9fb1b8", 0.82, 0.75)]:
        pts = [(0, H)]
        x = 0
        while x < W:
            pts.append((x, H * y - rng.uniform(0, 150) * s))
            x += rng.uniform(180, 280)
        pts.append((W, H))
        svg.add(polygon(pts, color, 0.95))
    svg.add(circle(W * 0.78, H * 0.18, 90, "#fffaf0", 0.9))

def v_meadow(svg, rng):
    grad_bg(svg, ["#cdeac0", "#eaf7d0"], 100)
    svg.add(rect(0, H * 0.65, W, H * 0.35, "#8fd694"))
    scatter(svg, rng, lambda cx, cy, s, r, o: flower_shape(cx, cy, s * 0.4, rng.choice(
        ["#ff9fd6", "#fff066", "#ff8080"]), "#ffe066", 5, o), 22, y_range=(H * 0.66, H * 0.97),
        size_range=(60, 120))
    svg.add(sun_shape(W * 0.5, H * 0.15, 110, "#ffe066", "#ffd166"))

def v_underwater(svg, rng):
    grad_bg(svg, ["#03045e", "#0077b6", "#00b4d8"], 100)
    scatter(svg, rng, lambda cx, cy, s, r, o: fish_shape(cx, cy, s * 0.5, rng.choice(
        ["#ff9f1c", "#ffd166", "#f15bb5", "#00f5d4"]), o, r), 10, rotate=True, size_range=(60, 130))
    scatter(svg, rng, lambda cx, cy, s, r, o: coral_shape(cx, cy, s * 0.6, rng.choice(
        ["#ff6f91", "#ff9671", "#ffc75f"]), o), 6, y_range=(H * 0.75, H * 0.98))

def v_rain_meadow(svg, rng):
    grad_bg(svg, ["#a8dadc", "#457b9d"], 100)
    rainbow_arcs(svg, rng, ["#ff9fbf", "#ffd39f", "#fff59f", "#c2f0c2", "#9fd8ff"])
    scatter(svg, rng, lambda cx, cy, s, r, o: raindrop_shape(cx, cy, s * 0.4, "#caf0f8", o * 0.7), 20,
            size_range=(50, 100))

cat("nature-scenes", "Nature Scenes", [
    ("Whispering Forest", v_forest),
    ("Sunny Beach Day", v_beach),
    ("Misty Mountains", v_mountains),
    ("Flower Meadow", v_meadow),
    ("Under the Sea", v_underwater),
    ("Rainbow After Rain", v_rain_meadow),
])

# ---- 5. Space & Planets ------------------------------------------------------
def starfield(svg, rng, n=160):
    for _ in range(n):
        svg.add(circle(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(2, 6), "#ffffff", rng.uniform(0.4, 1)))

def v_moon_stars(svg, rng):
    grad_bg(svg, ["#020024", "#090979", "#0d1b4c"], 100)
    starfield(svg, rng)
    svg.add(moon_shape(W * 0.75, H * 0.2, 160, "#fff8e0", 0.95))

def v_planets(svg, rng):
    grad_bg(svg, ["#0f0c29", "#302b63"], 60)
    starfield(svg, rng, 100)
    svg.add(planet_shape(W * 0.3, H * 0.3, 130, "#f4a261", "#ffd6a5", 0.95))
    svg.add(planet_shape(W * 0.72, H * 0.68, 200, "#2ec4b6", "#a6f0e3", 0.95))
    svg.add(circle(W * 0.15, H * 0.75, 60, "#ff9f9f", 0.9))

def v_rockets(svg, rng):
    grad_bg(svg, ["#1a1a40", "#3d2c8d"], 100)
    starfield(svg, rng, 90)
    scatter(svg, rng, lambda cx, cy, s, r, o: rocket_shape(cx, cy, s, rng.choice(
        ["#ff6b6b", "#4ecdc4", "#ffd166"]), "#ffffff", "#a6e3ff", o, r), 6, size_range=(140, 220), rotate=True)

def v_astronaut(svg, rng):
    grad_bg(svg, ["#000814", "#001d3d"], 100)
    starfield(svg, rng, 120)
    cx, cy = W * 0.5, H * 0.45
    svg.add(circle(cx, cy, 220, "#e9ecef", 0.95))
    svg.add(circle(cx, cy, 175, "#48cae4", 0.9))
    svg.add(circle(cx - 60, cy - 40, 30, "#ffffff", 0.7))
    svg.add(rect(cx - 140, cy + 190, 280, 260, "#e9ecef", rx=60))
    svg.add(circle(cx, cy + 320, 50, "#ff6b6b", 0.9))
    svg.add(moon_shape(W * 0.82, H * 0.15, 90, "#ffe8c2", 0.9))

def v_aliens(svg, rng):
    grad_bg(svg, ["#03071e", "#3a0ca3"], 100)
    starfield(svg, rng, 100)
    scatter(svg, rng, lambda cx, cy, s, r, o: alien_shape(cx, cy, s, rng.choice(
        ["#7bf1a8", "#9bf6ff", "#c8f7c5"]), o), 5, size_range=(160, 260))

def v_galaxy_swirl(svg, rng):
    grad_bg(svg, ["#3a0ca3", "#7209b7", "#0f0c29"], 45)
    starfield(svg, rng, 150)
    svg.add(circle(W * 0.5, H * 0.5, W * 0.35, svg.radial_gradient(["#f72585", "#7209b7", "#3a0ca3"]), 0.55))

cat("space-planets", "Space & Planets", [
    ("Moonlit Starry Night", v_moon_stars),
    ("Planet Parade", v_planets),
    ("Rocket Launch", v_rockets),
    ("Spacewalk Astronaut", v_astronaut),
    ("Friendly Aliens", v_aliens),
    ("Swirling Galaxy", v_galaxy_swirl),
])

# ---- 6. Flowers & Florals ----------------------------------------------------
def flower_field(colors, sky, title_center="#ffe066"):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: flower_shape(cx, cy, s * 0.5, rng.choice(colors),
                title_center, rng.choice([5, 6, 8]), o), 26, size_range=(70, 160))
    return build

cat("flowers-florals", "Flowers & Florals", [
    ("Rose Garden", flower_field(["#ff5c8a", "#ff8fa3", "#c9184a"], ["#fff0f5", "#ffe0eb"])),
    ("Wildflower Field", flower_field(["#ffd166", "#ef476f", "#06d6a0", "#118ab2"], ["#f1faee", "#dff7e0"])),
    ("Cherry Blossoms", flower_field(["#ffb7c5", "#ffc9de", "#ffe0ec"], ["#fff5f8", "#ffe8f0"], "#fff")),
    ("Sunflower Patch", flower_field(["#ffd60a", "#ffc300", "#ffb703"], ["#eafff1", "#dff7d0"], "#6b4423")),
    ("Tulip Bouquet", flower_field(["#e63946", "#ff8fa3", "#f4a261", "#e9c46a"], ["#f8f4ff", "#eee2ff"])),
    ("Daisy Chain", flower_field(["#ffffff", "#fdfcdc"], ["#e0f7fa", "#d0f4f7"], "#ffd60a")),
])

# ---- 7. Butterflies & Insects ------------------------------------------------
def bug_scene(colors, accent, sky, extra="butterfly"):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: flower_shape(cx, cy, s * 0.25, rng.choice(colors), accent, 5, o * 0.6),
                8, y_range=(H * 0.7, H * 0.97), size_range=(60, 100))
        if extra == "butterfly":
            scatter(svg, rng, lambda cx, cy, s, r, o: butterfly_shape(cx, cy, s * 0.55, rng.choice(colors), accent, o, r),
                    12, size_range=(90, 170), rotate=True)
        elif extra == "dragonfly":
            def dragon(cx, cy, s, r, o):
                items = [ellipse(cx, cy, s * 0.5, s * 0.12, "#118ab2", o),
                         ellipse(cx - s * 0.3, cy - s * 0.15, s * 0.35, s * 0.12, "#90e0ef", o * 0.8,
                                 transform=f"rotate(20 {cx-s*0.3} {cy-s*0.15})"),
                         ellipse(cx + s * 0.3, cy - s * 0.15, s * 0.35, s * 0.12, "#90e0ef", o * 0.8,
                                 transform=f"rotate(-20 {cx+s*0.3} {cy-s*0.15})"),
                         circle(cx - s * 0.28, cy, s * 0.1, "#023e8a", o)]
                return group(items, transform=f"rotate({r} {cx} {cy})")
            scatter(svg, rng, dragon, 12, size_range=(100, 180), rotate=True)
        else:  # ladybug
            def ladybug(cx, cy, s, r, o):
                items = [circle(cx, cy, s * 0.35, "#e63946", o),
                         f'<path d="M {cx} {cy-s*0.35} L {cx} {cy+s*0.35}" stroke="#1d1d1d" stroke-width="{s*0.04}"/>',
                         circle(cx - s * 0.12, cy - s * 0.1, s * 0.05, "#1d1d1d", o),
                         circle(cx + s * 0.12, cy - s * 0.1, s * 0.05, "#1d1d1d", o),
                         circle(cx - s * 0.15, cy + s * 0.1, s * 0.05, "#1d1d1d", o),
                         circle(cx, cy - s * 0.35, s * 0.15, "#1d1d1d", o)]
                return group(items, transform=f"rotate({r} {cx} {cy})")
            scatter(svg, rng, ladybug, 16, size_range=(80, 140), rotate=True)
    return build

cat("butterflies-insects", "Butterflies & Insects", [
    ("Monarch Meadow", bug_scene(["#ff9f1c", "#ffbf69"], "#1d1d1d", ["#fff3e0", "#ffe4c2"], "butterfly")),
    ("Blue Morpho Breeze", bug_scene(["#4361ee", "#4cc9f0"], "#03045e", ["#e0f7ff", "#c9ecff"], "butterfly")),
    ("Garden Butterflies", bug_scene(["#ff9fd6", "#c9a6ff", "#9fd8ff"], "#ffffff", ["#fff0fb", "#f3e0ff"], "butterfly")),
    ("Shimmery Dragonflies", bug_scene(["#90e0ef"], "#023e8a", ["#caf0f8", "#ade8f4"], "dragonfly")),
    ("Lucky Ladybugs", bug_scene(["#e63946"], "#1d1d1d", ["#eafff1", "#d0f4de"], "ladybug")),
    ("Butterfly Garden Party", bug_scene(["#ff5c8a", "#ffd166", "#06d6a0", "#4cc9f0"], "#1d1d1d",
                                          ["#fdf0ff", "#ffe6f7"], "butterfly")),
])

# ---- 8. Mermaids & Underwater -------------------------------------------------
def mermaid_scene(tail_colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: fish_shape(cx, cy, s * 0.35, rng.choice(
            ["#ffd166", "#ff9f1c", "#00f5d4"]), o * 0.8, r), 8, rotate=True, size_range=(50, 90))
        scatter(svg, rng, lambda cx, cy, s, r, o: mermaid_tail_shape(cx, cy, s, rng.choice(tail_colors),
                "#ffffff", o, r * 0.15), 4, size_range=(180, 260), rotate=True)
        scatter(svg, rng, lambda cx, cy, s, r, o: shell_shape(cx, cy, s * 0.4, "#ffe8f0", o), 10,
                y_range=(H * 0.8, H * 0.98), size_range=(50, 90))
    return build

cat("mermaids-underwater", "Mermaids & Underwater", [
    ("Mermaid Lagoon", mermaid_scene(["#00b4d8", "#48cae4"], ["#03045e", "#0077b6"])),
    ("Coral Reef Kingdom", mermaid_scene(["#f15bb5", "#ff9fd6"], ["#023e8a", "#0096c7"])),
    ("Sparkly Sea Shells", mermaid_scene(["#9b5de5", "#c8b6ff"], ["#0a4d68", "#088395"])),
    ("Emerald Mermaid Tide", mermaid_scene(["#06d6a0", "#2ec4b6"], ["#012a4a", "#013a63"])),
    ("Golden Sea Treasure", mermaid_scene(["#ffd166", "#ffb703"], ["#001d3d", "#003566"])),
    ("Rainbow Reef", mermaid_scene(["#ff6b6b", "#4ecdc4", "#ffe66d"], ["#04395e", "#70a9a1"])),
])

# ---- 9. Fairies & Magic -------------------------------------------------------
def fairy_scene(wing_colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: wings_shape(cx, cy, s, rng.choice(wing_colors), o * 0.85), 5,
                size_range=(140, 220))
        scatter(svg, rng, lambda cx, cy, s, r, o: sparkle_shape(cx, cy, s * 0.35, "#fff8e0", r, o), 30,
                size_range=(30, 90), rotate=True)
        for _ in range(5):
            svg.add(flower_shape(rng.uniform(100, W - 100), rng.uniform(H * 0.75, H * 0.95), 90,
                                  rng.choice(wing_colors), "#ffe066", 5, 0.9))
    return build

cat("fairies-magic", "Fairies & Magic", [
    ("Enchanted Forest Fairies", fairy_scene(["#9b5de5", "#c8b6ff"], ["#1b4332", "#2d6a4f"])),
    ("Sparkle Fairy Dust", fairy_scene(["#f15bb5", "#ff9fd6"], ["#2b2d42", "#3a0ca3"])),
    ("Moonlight Magic", fairy_scene(["#4cc9f0", "#a6e3ff"], ["#0d1b4c", "#1a1a40"])),
    ("Potion & Petals", fairy_scene(["#06d6a0", "#80ffdb"], ["#3a0ca3", "#7209b7"])),
    ("Golden Fairy Ring", fairy_scene(["#ffd166", "#fff3b0"], ["#4a2545", "#7b2d6e"])),
    ("Twilight Wings", fairy_scene(["#ff9fd6", "#c8b6ff", "#9bf6ff"], ["#0f0c29", "#302b63"])),
])

# ---- 10. Princesses & Castles ---------------------------------------------------
def princess_scene(fill_colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        svg.add(castle_shape(W * 0.5, H * 0.62, 550, rng.choice(fill_colors), "#6a4c93", 0.95))
        scatter(svg, rng, lambda cx, cy, s, r, o: crown_shape(cx, cy, s, rng.choice(fill_colors), "#ffe066", o),
                6, y_range=(H * 0.05, H * 0.4), size_range=(90, 150))
        scatter(svg, rng, lambda cx, cy, s, r, o: sparkle_shape(cx, cy, s * 0.3, "#ffffff", r, o), 24,
                y_range=(0, H * 0.5), rotate=True)
    return build

cat("princesses-castles", "Princesses & Castles", [
    ("Pink Palace Dreams", princess_scene(["#ff8fa3", "#ffb3c6"], ["#ffe0ec", "#ffd6e8"])),
    ("Lavender Castle", princess_scene(["#c8b6ff", "#b8c0ff"], ["#f3e8ff", "#e0d4ff"])),
    ("Golden Tiara Tower", princess_scene(["#ffd166", "#ffe8a3"], ["#fff8e0", "#ffefc2"])),
    ("Sky Blue Kingdom", princess_scene(["#a6e3ff", "#caf0f8"], ["#e0f7ff", "#cdeffd"])),
    ("Royal Ball Castle", princess_scene(["#e0aaff", "#c77dff"], ["#f8edff", "#eed5ff"])),
    ("Sunset Princess Tower", princess_scene(["#ff8fa3", "#ffb703"], ["#ffe5b4", "#ffd1a3"])),
])

# ---- 11. Hearts & Romance -----------------------------------------------------
def heart_scene(colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: heart_shape(cx, cy, s, rng.choice(colors), o, r), 26,
                size_range=(50, 140), rotate=True)
        scatter(svg, rng, lambda cx, cy, s, r, o: cloud_shape(cx, cy, s, "#ffffff", o * 0.5), 4,
                size_range=(150, 260))
    return build

cat("hearts-romance", "Hearts & Romance", [
    ("Love Bird Garden", heart_scene(["#ff5c8a", "#ff8fa3", "#ffb3c6"], ["#fff0f5", "#ffe0eb"])),
    ("Pink Cloud Hearts", heart_scene(["#ffffff", "#ffd6e8"], ["#ffc2d9", "#ff9fc1"])),
    ("Sweetheart Sparkle", heart_scene(["#ff5c8a", "#ffe066"], ["#fff5f8", "#ffe8f0"])),
    ("Romantic Rose Garden", heart_scene(["#e63946", "#ff8fa3"], ["#fff0f0", "#ffdada"])),
    ("Candy Heart Shower", heart_scene(["#ff9fd6", "#9fd8ff", "#fff066", "#9fffb0"], ["#fff8fb", "#ffeef7"])),
    ("Valentine Skies", heart_scene(["#ff4d6d", "#ff8fa3", "#ffccd5"], ["#590d22", "#800f2f"])),
])

# ---- 12. Fashion & Shopping ---------------------------------------------------
def dress_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    d = (f"M {cx-25*s} {cy-90*s} L {cx+25*s} {cy-90*s} L {cx+15*s} {cy-40*s} "
         f"C {cx+70*s} {cy-10*s}, {cx+80*s} {cy+90*s}, {cx+60*s} {cy+90*s} "
         f"L {cx-60*s} {cy+90*s} C {cx-80*s} {cy+90*s}, {cx-70*s} {cy-10*s}, {cx-15*s} {cy-40*s} Z")
    return path(d, fill, opacity)


def shoe_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    d = (f"M {cx-50*s} {cy} C {cx-55*s} {cy-40*s}, {cx-10*s} {cy-50*s}, {cx+10*s} {cy-35*s} "
         f"C {cx+30*s} {cy-45*s}, {cx+60*s} {cy-20*s}, {cx+55*s} {cy+10*s} "
         f"C {cx+55*s} {cy+25*s}, {cx-55*s} {cy+25*s}, {cx-50*s} {cy} Z")
    return path(d, fill, opacity)


def handbag_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 45 * s, cy - 10 * s, 90 * s, 70 * s, fill, rx=10 * s, opacity=opacity),
        f'<path d="M {cx-30*s} {cy-10*s} C {cx-30*s} {cy-55*s}, {cx+30*s} {cy-55*s}, {cx+30*s} {cy-10*s}" '
        f'fill="none" stroke="{fill}" stroke-width="{10*s:.1f}" opacity="{opacity:.2f}"/>',
        circle(cx, cy + 20 * s, 8 * s, "#ffe066", opacity),
    ]
    return group(items)


def fashion_scene(colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: dress_shape(cx, cy, s, rng.choice(colors), o), 6,
                size_range=(120, 190))
        scatter(svg, rng, lambda cx, cy, s, r, o: shoe_shape(cx, cy, s, rng.choice(colors), o), 6,
                size_range=(90, 140))
        scatter(svg, rng, lambda cx, cy, s, r, o: handbag_shape(cx, cy, s, rng.choice(colors), o), 5,
                size_range=(100, 150))
        scatter(svg, rng, lambda cx, cy, s, r, o: sparkle_shape(cx, cy, s * 0.3, "#ffffff", r, o), 14, rotate=True)
    return build

cat("fashion-shopping", "Fashion & Shopping", [
    ("Pink Boutique Vibes", fashion_scene(["#ff8fa3", "#ffb3c6", "#ffe0ec"], ["#fff0f5", "#ffe6ee"])),
    ("Runway Ready", fashion_scene(["#9b5de5", "#f15bb5", "#4cc9f0"], ["#2b2d42", "#3a0ca3"])),
    ("Sunny Shopping Day", fashion_scene(["#ffd166", "#ff9f1c", "#06d6a0"], ["#fff8e0", "#ffefc2"])),
    ("Chic Pastel Closet", fashion_scene(["#c8b6ff", "#a6e3ff", "#ffd6e8"], ["#f3f0ff", "#eae4ff"])),
    ("Glam Night Out", fashion_scene(["#ffd60a", "#f15bb5", "#9b5de5"], ["#10002b", "#240046"])),
    ("Bright Boutique Bags", fashion_scene(["#ff6b6b", "#4ecdc4", "#ffe66d"], ["#fff5f8", "#ffe8f0"])),
])

# ---- 13. Unicorns & Fantasy ----------------------------------------------------
def unicorn_scene(mane_colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        for _ in range(3):
            cx, cy = rng.uniform(200, W - 200), rng.uniform(300, H - 300)
            svg.add(animal_face_shape(cx, cy, rng.uniform(260, 360), "#ffffff", "#ffd6ec", "unicorn", 0.97))
        rainbow_arcs(svg, rng, mane_colors)
        scatter(svg, rng, lambda cx, cy, s, r, o: sparkle_shape(cx, cy, s * 0.35, "#ffffff", r, o), 22,
                y_range=(0, H * 0.5), rotate=True)
        scatter(svg, rng, lambda cx, cy, s, r, o: cloud_shape(cx, cy, s, "#ffffff", o * 0.8), 4,
                size_range=(140, 220), y_range=(0, H * 0.4))
    return build

cat("unicorns-fantasy", "Unicorns & Fantasy", [
    ("Rainbow Unicorn Dream", unicorn_scene(["#ff9fbf", "#ffd39f", "#fff59f", "#c2f0c2", "#9fd8ff", "#c9a6ff"],
                                             ["#f3e8ff", "#e0f7ff"])),
    ("Flying Unicorns", unicorn_scene(["#c9a6ff", "#9fd8ff", "#ff9fd6"], ["#dff3ff", "#eae4ff"])),
    ("Magical Cloud Kingdom", unicorn_scene(["#ffe0ec", "#e0d4ff", "#d4f4ff"], ["#fff8fb", "#f3e8ff"])),
    ("Starlight Unicorn", unicorn_scene(["#4cc9f0", "#9b5de5", "#f15bb5"], ["#1a1a40", "#302b63"])),
    ("Cotton Candy Unicorn", unicorn_scene(["#ffb3c6", "#c8b6ff", "#a6e3ff"], ["#ffe6f2", "#e6f0ff"])),
    ("Golden Horn Fantasy", unicorn_scene(["#ffd166", "#ff9f1c", "#ffe8a3"], ["#fff8e0", "#ffefc2"])),
])

# ---- 14. Cats & Kittens --------------------------------------------------------
def cats_scene(colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: animal_face_shape(cx, cy, s, rng.choice(colors),
                rng.choice(colors), "kitten", o), 7, size_range=(200, 300))
        scatter(svg, rng, lambda cx, cy, s, r, o: paw_shape(cx, cy, s * 0.35, rng.choice(colors), o * 0.5, r),
                14, rotate=True, size_range=(60, 110))
    return build

cat("cats-kittens", "Cats & Kittens", [
    ("Orange Tabby Squad", cats_scene(["#f2994a", "#ffb703"], ["#fff3e0", "#ffe4c2"])),
    ("Black Cat Magic", cats_scene(["#2b2b2b", "#495057"], ["#e0d4ff", "#c8b6ff"])),
    ("Fluffy White Kittens", cats_scene(["#ffffff", "#f8f9fa"], ["#e0f7ff", "#caf0f8"])),
    ("Calico Cuties", cats_scene(["#f2c14e", "#f28482", "#ffffff"], ["#fff0f5", "#ffe4ec"])),
    ("Grey Tabby Nap Time", cats_scene(["#adb5bd", "#6c757d"], ["#eafff1", "#d0f4de"])),
    ("Kitten Pattern Party", cats_scene(["#ff9f1c", "#9b5de5", "#4cc9f0", "#ffd166"], ["#fdf0ff", "#ffe6f7"])),
])

# ---- 15. Bows & Ribbons --------------------------------------------------------
def bows_scene(colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: bow_shape(cx, cy, s, rng.choice(colors), o, r), 16,
                size_range=(60, 140), rotate=True)
        scatter(svg, rng, lambda cx, cy, s, r, o: ribbon_shape(cx, cy, s, rng.choice(colors), o, r), 10,
                size_range=(80, 160), rotate=True)
    return build

cat("bows-ribbons", "Bows & Ribbons", [
    ("Pink Polka Bows", bows_scene(["#ff8fa3", "#ffb3c6"], ["#fff0f5", "#ffe0eb"])),
    ("Lace & Ribbon Trim", bows_scene(["#c8b6ff", "#e0aaff"], ["#f3e8ff", "#eae4ff"])),
    ("Gingham Bow Party", bows_scene(["#ff6b6b", "#4ecdc4", "#ffe66d"], ["#fff8e0", "#ffefc2"])),
    ("Satin Bow Shine", bows_scene(["#f15bb5", "#9b5de5"], ["#2b2d42", "#3a0ca3"])),
    ("Sweet Gift Ribbons", bows_scene(["#06d6a0", "#ffd166", "#ef476f"], ["#fff5f8", "#ffe8f0"])),
    ("Golden Bow Sparkle", bows_scene(["#ffd166", "#ffe8a3"], ["#fff8e0", "#ffe9c2"])),
])

# ---- 16. Sports & Games --------------------------------------------------------
def v_soccer(svg, rng):
    grad_bg(svg, ["#a8e063", "#56ab2f"], 90)
    scatter(svg, rng, lambda cx, cy, s, r, o: soccer_ball_shape(cx, cy, s * 0.5, "#ffffff", "#1d1d1d", o), 6,
            size_range=(140, 220))

def v_basketball(svg, rng):
    grad_bg(svg, ["#ff9f1c", "#f77f00"], 90)
    scatter(svg, rng, lambda cx, cy, s, r, o: basketball_shape(cx, cy, s * 0.5, "#e85d04", "#1d1d1d", o), 6,
            size_range=(140, 220))

def v_skate(svg, rng):
    grad_bg(svg, ["#4cc9f0", "#4361ee"], 90)
    scatter(svg, rng, lambda cx, cy, s, r, o: skateboard_shape(cx, cy, s, rng.choice(
        ["#ff6b6b", "#ffe66d", "#06d6a0"]), "#1d1d1d", o, r), 10, size_range=(120, 200), rotate=True)
    scatter(svg, rng, lambda cx, cy, s, r, o: star_shape(cx, cy, s * 0.3, "#ffffff", 4, r, o * 0.7), 14,
            rotate=True)

def v_gameon(svg, rng):
    grad_bg(svg, ["#3a0ca3", "#7209b7", "#f72585"], 60)
    def controller(cx, cy, s, r, o):
        items = [rect(cx - s * 0.6, cy - s * 0.25, s * 1.2, s * 0.5, "#1d1d1d", rx=s * 0.25, opacity=o),
                 circle(cx - s * 0.3, cy, s * 0.12, "#ffffff", o),
                 circle(cx + s * 0.25, cy - s * 0.1, s * 0.08, "#ff6b6b", o),
                 circle(cx + s * 0.35, cy + s * 0.05, s * 0.08, "#4ecdc4", o)]
        return group(items, transform=f"rotate({r} {cx} {cy})")
    scatter(svg, rng, controller, 8, size_range=(140, 220), rotate=True)
    scatter(svg, rng, lambda cx, cy, s, r, o: star_shape(cx, cy, s * 0.3, "#ffe66d", 5, r, o), 16, rotate=True)

def v_multi_sport(svg, rng):
    grad_bg(svg, ["#ffe066", "#ff9f1c"], 90)
    scatter(svg, rng, lambda cx, cy, s, r, o: soccer_ball_shape(cx, cy, s * 0.35, "#ffffff", "#1d1d1d", o), 4,
            size_range=(110, 160))
    scatter(svg, rng, lambda cx, cy, s, r, o: basketball_shape(cx, cy, s * 0.35, "#e85d04", "#1d1d1d", o), 4,
            size_range=(110, 160))
    scatter(svg, rng, lambda cx, cy, s, r, o: star_shape(cx, cy, s * 0.25, "#ffffff", 5, r, o * 0.8), 10, rotate=True)

def v_medal(svg, rng):
    grad_bg(svg, ["#ffd166", "#f77f00"], 90)
    def medal(cx, cy, s, r, o):
        items = [rect(cx - s * 0.08, cy - s, s * 0.16, s * 0.8, "#ef476f", opacity=o),
                 circle(cx, cy + s * 0.15, s * 0.4, "#ffe066", o),
                 circle(cx, cy + s * 0.15, s * 0.26, "#fff3b0", o)]
        return group(items, transform=f"rotate({r} {cx} {cy})")
    scatter(svg, rng, medal, 8, size_range=(120, 200), rotate=True)

cat("sports-games", "Sports & Games", [
    ("Soccer Star", v_soccer),
    ("Basketball Bounce", v_basketball),
    ("Skateboard Squad", v_skate),
    ("Game On!", v_gameon),
    ("All-Star Sports Mix", v_multi_sport),
    ("Champion Medals", v_medal),
])

# ---- 17. Dinosaurs & Prehistoric -------------------------------------------------
def dino_scene(colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: dino_shape(cx, cy, s, rng.choice(colors), "#2d6a4f", o), 6,
                size_range=(170, 260))
        for _ in range(2):
            cx, cy = rng.uniform(150, W - 150), rng.uniform(H * 0.1, H * 0.3)
            svg.add(triangle_shape(cx, cy, 130, "#6c757d", 0.9))
            svg.add(circle(cx, cy - 150, 30, "#ff9f1c", 0.9))
    return build

cat("dinosaurs-prehistoric", "Dinosaurs & Prehistoric", [
    ("Green Dino Jungle", dino_scene(["#52b788", "#2d6a4f"], ["#d8f3dc", "#b7e4c7"])),
    ("Volcano Valley", dino_scene(["#e76f51", "#f4a261"], ["#ffddd2", "#ffc8a2"])),
    ("Purple Prehistoric Pals", dino_scene(["#9b5de5", "#c8b6ff"], ["#f3e8ff", "#e0d4ff"])),
    ("Blue Dino Discovery", dino_scene(["#4cc9f0", "#4361ee"], ["#dff3ff", "#c9ecff"])),
    ("Orange Roar", dino_scene(["#ff9f1c", "#f3722c"], ["#fff3e0", "#ffe4c2"])),
    ("Fossil Hunt Adventure", dino_scene(["#588157", "#a3b18a"], ["#f0ead2", "#ede0c8"])),
])

# ---- 18. Vehicles ----------------------------------------------------------------
def plane_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        ellipse(cx, cy, 80 * s, 22 * s, fill, opacity),
        polygon([(cx-10*s, cy), (cx-45*s, cy-45*s), (cx-15*s, cy)], fill, opacity),
        polygon([(cx-10*s, cy), (cx-45*s, cy+45*s), (cx-15*s, cy)], fill, opacity),
        polygon([(cx+65*s, cy), (cx+90*s, cy-20*s), (cx+90*s, cy+20*s)], fill, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def balloon_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        circle(cx, cy - 20 * s, 55 * s, fill, opacity),
        polygon([(cx-45*s, cy+10*s), (cx+45*s, cy+10*s), (cx+22*s, cy+50*s), (cx-22*s, cy+50*s)], "#f4a261", opacity),
        line(cx - 40 * s, cy + 20 * s, cx - 20 * s, cy + 50 * s, "#5b3a29", 2, opacity),
        line(cx + 40 * s, cy + 20 * s, cx + 20 * s, cy + 50 * s, "#5b3a29", 2, opacity),
    ]
    return group(items)


def train_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 70 * s, cy - 40 * s, 140 * s, 70 * s, fill, rx=10 * s, opacity=opacity),
        rect(cx - 50 * s, cy - 70 * s, 60 * s, 40 * s, fill, rx=6 * s, opacity=opacity),
        circle(cx - 40 * s, cy + 40 * s, 16 * s, "#1d1d1d", opacity),
        circle(cx, cy + 40 * s, 16 * s, "#1d1d1d", opacity),
        circle(cx + 40 * s, cy + 40 * s, 16 * s, "#1d1d1d", opacity),
    ]
    return group(items)


def vehicle_scene(kind, colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        if kind == "car":
            scatter(svg, rng, lambda cx, cy, s, r, o: car_shape(cx, cy, s, rng.choice(colors), "#2b2b2b", o), 7,
                    size_range=(150, 230))
        elif kind == "plane":
            scatter(svg, rng, lambda cx, cy, s, r, o: plane_shape(cx, cy, s, rng.choice(colors), o, r), 6,
                    size_range=(140, 220), rotate=True)
            scatter(svg, rng, lambda cx, cy, s, r, o: cloud_shape(cx, cy, s, "#ffffff", o * 0.7), 5,
                    size_range=(120, 200))
        elif kind == "balloon":
            scatter(svg, rng, lambda cx, cy, s, r, o: balloon_shape(cx, cy, s, rng.choice(colors), o), 8,
                    size_range=(140, 220))
        elif kind == "train":
            scatter(svg, rng, lambda cx, cy, s, r, o: train_shape(cx, cy, s, rng.choice(colors), o), 6,
                    size_range=(150, 230))
        else:  # mixed
            fns = [lambda cx, cy, s, r, o: car_shape(cx, cy, s, rng.choice(colors), "#2b2b2b", o),
                   lambda cx, cy, s, r, o: plane_shape(cx, cy, s, rng.choice(colors), o, r),
                   lambda cx, cy, s, r, o: balloon_shape(cx, cy, s, rng.choice(colors), o)]
            for _ in range(10):
                fn = rng.choice(fns)
                svg.add(fn(rng.uniform(120, W - 120), rng.uniform(120, H - 120), rng.uniform(130, 200),
                            rng.uniform(0, 360), rng.uniform(0.85, 1)))
    return build

cat("vehicles", "Vehicles", [
    ("Speedy Car Parade", vehicle_scene("car", ["#ff6b6b", "#4ecdc4", "#ffe66d"], ["#e0f7fa", "#caf0f8"])),
    ("Sky High Airplanes", vehicle_scene("plane", ["#4361ee", "#ffffff", "#f4a261"], ["#a8e6ff", "#d6f0ff"])),
    ("Hot Air Balloon Ride", vehicle_scene("balloon", ["#ff9f1c", "#ef476f", "#06d6a0", "#4cc9f0"],
                                            ["#fff3e0", "#ffe4c2"])),
    ("Choo Choo Train", vehicle_scene("train", ["#e63946", "#457b9d", "#ffb703"], ["#dff3ff", "#c9ecff"])),
    ("Vehicle Adventure Mix", vehicle_scene("mixed", ["#ff6b6b", "#4ecdc4", "#ffd166", "#9b5de5"],
                                             ["#fff8e0", "#ffefc2"])),
    ("City Traffic Fun", vehicle_scene("car", ["#3a86ff", "#ffbe0b", "#fb5607"], ["#f1faee", "#dff7e0"])),
])

# ---- 19. Superheroes & Action --------------------------------------------------
def hero_scene(colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: mask_shape(cx, cy, s, rng.choice(colors), o), 8,
                size_range=(110, 180))
        scatter(svg, rng, lambda cx, cy, s, r, o: star_shape(cx, cy, s * 0.35, "#ffe66d", 5, r, o), 14, rotate=True)
        scatter(svg, rng, lambda cx, cy, s, r, o: lightning_shape(cx, cy, s * 0.4, "#ffe66d", o), 8, size_range=(80, 150))
    return build

cat("superheroes-action", "Superheroes & Action", [
    ("Red Cape Hero", hero_scene(["#ef476f", "#ff6b6b"], ["#fff3e0", "#ffe4c2"])),
    ("Blue Blast Hero", hero_scene(["#4361ee", "#4cc9f0"], ["#e0f7fa", "#caf0f8"])),
    ("Comic Book Pow!", hero_scene(["#ffd166", "#ef476f", "#4361ee"], ["#fff8e0", "#ffe9c2"])),
    ("Purple Power Hero", hero_scene(["#7209b7", "#9b5de5"], ["#f3e8ff", "#e0d4ff"])),
    ("Green Guardian", hero_scene(["#2d6a4f", "#52b788"], ["#d8f3dc", "#b7e4c7"])),
    ("Night Sky Hero Squad", hero_scene(["#ffd166", "#4cc9f0", "#ef476f"], ["#03071e", "#3a0ca3"])),
])

# ---- 20. Food & Treats -----------------------------------------------------------
def food_scene(kind, colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        if kind == "cupcake":
            scatter(svg, rng, lambda cx, cy, s, r, o: cupcake_shape(cx, cy, s, rng.choice(colors), "#ffffff",
                    "#ef476f", o), 8, size_range=(130, 200))
        elif kind == "icecream":
            scatter(svg, rng, lambda cx, cy, s, r, o: ice_cream_shape(cx, cy, s, "#f4a261",
                    rng.sample(colors, 2), o), 7, size_range=(140, 210))
        elif kind == "candy":
            def candy(cx, cy, s, r, o):
                items = [ellipse(cx, cy, s * 0.35, s * 0.2, rng.choice(colors), o),
                         polygon([(cx - s * 0.35, cy), (cx - s * 0.55, cy - s * 0.2), (cx - s * 0.55, cy + s * 0.2)],
                                 rng.choice(colors), o),
                         polygon([(cx + s * 0.35, cy), (cx + s * 0.55, cy - s * 0.2), (cx + s * 0.55, cy + s * 0.2)],
                                 rng.choice(colors), o)]
                return group(items, transform=f"rotate({r} {cx} {cy})")
            scatter(svg, rng, candy, 16, size_range=(90, 160), rotate=True)
        elif kind == "pizza":
            def slice_(cx, cy, s, r, o):
                items = [polygon([(cx, cy - s), (cx - s * 0.5, cy + s * 0.5), (cx + s * 0.5, cy + s * 0.5)],
                                  "#ffd166", o),
                         circle(cx - s * 0.1, cy, s * 0.08, "#e63946", o),
                         circle(cx + s * 0.15, cy + s * 0.2, s * 0.08, "#e63946", o),
                         circle(cx, cy + s * 0.35, s * 0.08, "#588157", o)]
                return group(items, transform=f"rotate({r} {cx} {cy})")
            scatter(svg, rng, slice_, 10, size_range=(110, 180), rotate=True)
        else:  # donuts
            def donut(cx, cy, s, r, o):
                items = [circle(cx, cy, s * 0.5, rng.choice(colors), o), circle(cx, cy, s * 0.18, sky[0], o)]
                for i in range(6):
                    a = math.radians(i * 60)
                    items.append(circle(cx + s * 0.32 * math.cos(a), cy + s * 0.32 * math.sin(a), s * 0.05,
                                         "#ffffff", o))
                return group(items, transform=f"rotate({r} {cx} {cy})")
            scatter(svg, rng, donut, 9, size_range=(130, 200), rotate=True)
    return build

cat("food-treats", "Food & Treats", [
    ("Cupcake Party", food_scene("cupcake", ["#ff8fa3", "#ffd6e8", "#c8b6ff"], ["#fff0f5", "#ffe6ee"])),
    ("Ice Cream Dreams", food_scene("icecream", ["#ffb3c6", "#a6e3ff", "#fff066", "#c8b6ff"], ["#fff8e0", "#ffefc2"])),
    ("Candy Land", food_scene("candy", ["#ef476f", "#ffd166", "#06d6a0", "#4cc9f0"], ["#fdf0ff", "#ffe6f7"])),
    ("Pizza Party", food_scene("pizza", ["#ffd166"], ["#fff3e0", "#ffe4c2"])),
    ("Donut Delight", food_scene("donut", ["#ff8fa3", "#c8b6ff", "#ffd166"], ["#fff0f5", "#ffe6ee"])),
    ("Sweet Treats Mix", food_scene("cupcake", ["#06d6a0", "#4cc9f0", "#ff9f1c"], ["#eafff1", "#d0f4de"])),
])

# ---- 21. Music & Dance -----------------------------------------------------------
def music_scene(colors, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        scatter(svg, rng, lambda cx, cy, s, r, o: musical_note_shape(cx, cy, s, rng.choice(colors), o, r), 20,
                size_range=(70, 150), rotate=True)
        scatter(svg, rng, lambda cx, cy, s, r, o: star_shape(cx, cy, s * 0.25, "#ffffff", 5, r, o * 0.7), 10,
                rotate=True)
    return build

cat("music-dance", "Music & Dance", [
    ("Musical Note Melody", music_scene(["#ef476f", "#ffd166", "#4cc9f0"], ["#fff8e0", "#ffefc2"])),
    ("Dance Party Lights", music_scene(["#f72585", "#9b5de5", "#4cc9f0", "#ffe66d"], ["#10002b", "#3a0ca3"])),
    ("Pastel Piano Keys", music_scene(["#ffb3c6", "#c8b6ff", "#a6e3ff"], ["#fff0f5", "#eae4ff"])),
    ("Rockstar Rhythm", music_scene(["#ff6b6b", "#ffd166", "#06d6a0"], ["#03071e", "#3a0ca3"])),
    ("Sunshine Song", music_scene(["#ffd166", "#ff9f1c", "#ef476f"], ["#fff3e0", "#ffe4c2"])),
    ("Twinkle Tune Notes", music_scene(["#9b5de5", "#f15bb5", "#4cc9f0"], ["#e0f7fa", "#dbe7ff"])),
])

# ---- 22. Winter & Holiday --------------------------------------------------------
def snowman_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        circle(cx, cy + 60 * s, 55 * s, "#ffffff", opacity),
        circle(cx, cy - 10 * s, 40 * s, "#ffffff", opacity),
        circle(cx, cy - 65 * s, 28 * s, "#ffffff", opacity),
        polygon([(cx, cy - 65 * s), (cx + 30 * s, cy - 60 * s), (cx, cy - 55 * s)], "#f4a261", opacity),
        circle(cx - 10 * s, cy - 70 * s, 4 * s, "#1d1d1d", opacity),
        circle(cx + 10 * s, cy - 70 * s, 4 * s, "#1d1d1d", opacity),
        circle(cx, cy - 12 * s, 5 * s, "#1d1d1d", opacity),
        circle(cx, cy + 4 * s, 5 * s, "#1d1d1d", opacity),
        circle(cx, cy + 20 * s, 5 * s, "#1d1d1d", opacity),
    ]
    return group(items)


def winter_scene(kind, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        if kind == "snowflakes":
            scatter(svg, rng, lambda cx, cy, s, r, o: snowflake_shape(cx, cy, s * 0.4, "#ffffff", o), 24,
                    size_range=(60, 140))
        elif kind == "snowman":
            scatter(svg, rng, lambda cx, cy, s, r, o: snowman_shape(cx, cy, s, o), 5, size_range=(160, 240))
            scatter(svg, rng, lambda cx, cy, s, r, o: circle(cx, cy, s * 0.1, "#ffffff", o), 30, size_range=(20, 60))
        elif kind == "christmas":
            def tree(cx, cy, s, r, o):
                items = [triangle_shape(cx, cy - s * 0.3, s * 0.5, "#2d6a4f", o),
                         triangle_shape(cx, cy, s * 0.65, "#2d6a4f", o),
                         triangle_shape(cx, cy + s * 0.35, s * 0.8, "#2d6a4f", o),
                         rect(cx - s * 0.08, cy + s * 0.75, s * 0.16, s * 0.3, "#6b4423", opacity=o),
                         star_shape(cx, cy - s * 0.85, s * 0.15, "#ffd166", 5, 0, o)]
                for i in range(6):
                    items.append(circle(cx + rng.uniform(-s * 0.4, s * 0.4), cy + rng.uniform(-s * 0.1, s * 0.9),
                                         s * 0.05, rng.choice(["#ef476f", "#ffd166", "#4cc9f0"]), o))
                return group(items)
            scatter(svg, rng, tree, 5, size_range=(180, 260))
        else:  # decorations / ornaments
            def ornament(cx, cy, s, r, o):
                c = rng.choice(["#ef476f", "#ffd166", "#4cc9f0", "#06d6a0"])
                items = [line(cx, cy - s * 0.5, cx, cy - s * 0.35, "#ffe066", s * 0.05, o),
                         circle(cx, cy, s * 0.35, c, o), ellipse(cx - s * 0.1, cy - s * 0.1, s * 0.1, s * 0.06,
                         "#ffffff", o * 0.6)]
                return group(items, transform=f"rotate({r*0.2} {cx} {cy})")
            scatter(svg, rng, ornament, 14, size_range=(90, 160), rotate=True)
    return build

cat("winter-holiday", "Winter & Holiday", [
    ("Snowflake Sparkle", winter_scene("snowflakes", ["#dbe9ff", "#a8c6ff"])),
    ("Frosty the Snowman", winter_scene("snowman", ["#8ecae6", "#219ebc"])),
    ("Christmas Tree Cheer", winter_scene("christmas", ["#eafff1", "#d0f4de"])),
    ("Holiday Ornaments", winter_scene("ornaments", ["#590d22", "#800f2f"])),
    ("Winter Wonderland", winter_scene("snowflakes", ["#03045e", "#0077b6"])),
    ("Candy Cane Christmas", winter_scene("ornaments", ["#fff0f0", "#ffdada"])),
])

# ---- 23. Summer & Beach ------------------------------------------------------------
def summer_scene(kind, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        if kind == "surf":
            def board(cx, cy, s, r, o):
                items = [ellipse(cx, cy, s * 0.18, s * 0.7, rng.choice(["#ff6b6b", "#4cc9f0", "#ffe66d"]), o)]
                return group(items, transform=f"rotate({r} {cx} {cy})")
            scatter(svg, rng, board, 8, size_range=(140, 220), rotate=True)
            svg.add(sun_shape(W * 0.5, H * 0.15, 110, "#ffe066", "#ffd166"))
        elif kind == "sandcastle":
            scatter(svg, rng, lambda cx, cy, s, r, o: sandcastle_shape(cx, cy, s, "#ffd8a8", o), 5,
                    y_range=(H * 0.55, H * 0.85), size_range=(140, 220))
            svg.add(rect(0, H * 0.85, W, H * 0.15, "#4cc9f0", opacity=0.8))
        elif kind == "icecream":
            scatter(svg, rng, lambda cx, cy, s, r, o: ice_cream_shape(cx, cy, s, "#f4a261",
                    ["#ffb3c6", "#a6e3ff"], o), 7, size_range=(140, 210))
        else:  # palm sunset
            for i, (color, y, s) in enumerate([("#f4a261", 0.6, 1)]):
                pass
            svg.add(circle(W * 0.5, H * 0.55, W * 0.22, "#ffe066", 0.95))
            for _ in range(4):
                svg.add(palm_tree_shape(rng.uniform(150, W - 150), H * rng.uniform(0.55, 0.72), 240,
                                         "#3a2a1a", "#2d6a4f", 0.95))
    return build

cat("summer-beach", "Summer & Beach", [
    ("Surf's Up", summer_scene("surf", ["#00b4d8", "#90e0ef"])),
    ("Sandcastle Shores", summer_scene("sandcastle", ["#a8e6ff", "#dff7ff"])),
    ("Summer Ice Cream", summer_scene("icecream", ["#fff3e0", "#ffe4c2"])),
    ("Palm Tree Sunset", summer_scene("palm", ["#ff9f7b", "#ff6f91"])),
    ("Beach Ball Bounce", summer_scene("surf", ["#ffe066", "#ff9f1c"])),
    ("Tropical Paradise", summer_scene("palm", ["#06d6a0", "#4cc9f0"])),
])

# ---- 24. Weather --------------------------------------------------------------------
def weather_scene(kind, sky):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        if kind == "rainbow":
            rainbow_arcs(svg, rng, ["#ff9fbf", "#ffd39f", "#fff59f", "#c2f0c2", "#9fd8ff", "#c9a6ff"])
            scatter(svg, rng, lambda cx, cy, s, r, o: cloud_shape(cx, cy, s, "#ffffff", o), 4,
                    size_range=(140, 220), y_range=(H * 0.75, H * 0.95))
        elif kind == "storm":
            scatter(svg, rng, lambda cx, cy, s, r, o: cloud_shape(cx, cy, s, "#495057", o), 6,
                    size_range=(160, 260), y_range=(0, H * 0.5))
            scatter(svg, rng, lambda cx, cy, s, r, o: lightning_shape(cx, cy, s * 0.5, "#ffe66d", o), 6,
                    y_range=(H * 0.4, H * 0.9), size_range=(100, 180))
        elif kind == "sunny":
            svg.add(sun_shape(W * 0.5, H * 0.35, 220, "#ffe066", "#ffd166"))
            scatter(svg, rng, lambda cx, cy, s, r, o: cloud_shape(cx, cy, s, "#ffffff", o * 0.8), 4,
                    size_range=(120, 200), y_range=(H * 0.6, H * 0.9))
        else:  # cloudy / rain
            scatter(svg, rng, lambda cx, cy, s, r, o: cloud_shape(cx, cy, s, "#ffffff", o), 8,
                    size_range=(150, 240))
            scatter(svg, rng, lambda cx, cy, s, r, o: raindrop_shape(cx, cy, s * 0.4, "#a6e3ff", o), 20,
                    y_range=(H * 0.5, H * 0.95), size_range=(50, 100))
    return build

cat("weather", "Weather", [
    ("Rainbow Clouds", weather_scene("rainbow", ["#a8dadc", "#457b9d"])),
    ("Thunderstorm Adventure", weather_scene("storm", ["#2b2d42", "#495057"])),
    ("Sunny Blue Skies", weather_scene("sunny", ["#90e0ef", "#caf0f8"])),
    ("April Showers", weather_scene("cloudy", ["#dbe9ff", "#a8c6ff"])),
    ("Golden Sunshine", weather_scene("sunny", ["#ffe066", "#ffd166"])),
    ("Misty Rain Clouds", weather_scene("cloudy", ["#8ecae6", "#219ebc"])),
])

# ---- 25. Neon & Bold ------------------------------------------------------------------
def neon_scene(colors, sky=None):
    sky = sky or ["#0d0221", "#190535"]
    def build(svg, rng):
        grad_bg(svg, sky, 120)
        scatter(svg, rng, lambda cx, cy, s, r, o: star_shape(cx, cy, s * 0.4, rng.choice(colors), 5, r, o), 18,
                size_range=(60, 140), rotate=True)
        scatter(svg, rng, lambda cx, cy, s, r, o: f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s*0.3:.1f}" '
                f'fill="none" stroke="{rng.choice(colors)}" stroke-width="6" opacity="{o:.2f}"/>', 10,
                size_range=(80, 200))
        scatter(svg, rng, lambda cx, cy, s, r, o: lightning_shape(cx, cy, s * 0.4, rng.choice(colors), o), 8,
                size_range=(80, 150))
    return build

cat("neon-bold", "Neon & Bold", [
    ("Electric Pink Glow", neon_scene(["#ff006e", "#fb5607"])),
    ("Neon Green Grid", neon_scene(["#39ff14", "#00f5d4"])),
    ("Ultraviolet Nights", neon_scene(["#9b5de5", "#f15bb5", "#00bbf9"])),
    ("Cyber Yellow Bolt", neon_scene(["#ffe600", "#ff006e"])),
    ("Neon Rainbow Rave", neon_scene(["#ff006e", "#ffbe0b", "#3a86ff", "#8338ec", "#06d6a0"])),
    ("Blacklight Blast", neon_scene(["#00f5d4", "#f15bb5", "#fee440"])),
])


# --------------------------------------------------------------------------
# Build everything
# --------------------------------------------------------------------------

def slugify(title):
    out = []
    for ch in title.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_":
            out.append("-")
    s = "".join(out)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    entries = []
    total = 0
    for cat_def in CATS:
        slug = cat_def["slug"]
        cat_dir = os.path.join(OUT_DIR, slug)
        os.makedirs(cat_dir, exist_ok=True)
        for i, (title, builder) in enumerate(cat_def["variants"], start=1):
            rng = random.Random(f"{slug}-{i}-{title}")
            svg = Svg()
            builder(svg, rng)
            file_slug = slugify(title)
            filename = f"{file_slug}.svg"
            filepath = os.path.join(cat_dir, filename)
            with open(filepath, "w") as f:
                f.write(svg.render())
            entries.append({
                "id": f"{slug}/{file_slug}",
                "title": title,
                "category": slug,
                "categoryName": cat_def["name"],
                "filename": f"images/backgrounds/{slug}/{filename}",
                "credit": "Original artwork generated for this app",
                "tags": [slug.replace("-", " "), cat_def["name"].lower()],
            })
            total += 1
    with open(JSON_PATH, "w") as f:
        json.dump({
            "categories": [{"slug": c["slug"], "name": c["name"]} for c in CATS],
            "backgrounds": entries,
        }, f, indent=2)
    print(f"Generated {total} backgrounds across {len(CATS)} categories.")


if __name__ == "__main__":
    main()
