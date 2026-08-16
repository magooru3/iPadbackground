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
import re

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

    def blur_filter(self, std_dev):
        fid = self.uid("blur")
        self.add_def(
            f'<filter id="{fid}" x="-60%" y="-60%" width="220%" height="220%">'
            f'<feGaussianBlur stdDeviation="{std_dev}"/></filter>'
        )
        return fid

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
# "Realistic style" rendering helpers
# --------------------------------------------------------------------------
# These don't fake photography -- they're a second, more polished vector
# treatment layered around the same flat silhouette shapes used everywhere
# else: a soft blurred-bokeh backdrop (instead of a flat gradient), a
# blurred contact shadow under each subject, fine "fur"/texture strokes
# over the body, a soft directional highlight, and a vignette. Together
# these read as meaningfully more lifelike/detailed than the flat cartoon
# style while staying 100% original vector art.

def shadow_ellipse(cx, cy, rx, ry, blur_id, opacity=0.3):
    return (f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'fill="#000000" opacity="{opacity:.2f}" filter="url(#{blur_id})"/>')


def glow_highlight(svg, cx, cy, r, opacity=0.35):
    gid = svg.radial_gradient(["#ffffffcc", "#ffffff00"], cx=40, cy=35, r=65)
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{gid}" opacity="{opacity:.2f}"/>'


def vignette(svg, opacity=0.22):
    gid = svg.radial_gradient(["#00000000", "#0b0b1a"], cx=50, cy=45, r=72)
    return f'<rect x="0" y="0" width="{W}" height="{H}" fill="{gid}" opacity="{opacity:.2f}"/>'


def fur_texture(cx, cy, r, color, count, rng, opacity_range=(0.25, 0.55), length_range=(6, 16)):
    items = []
    for _ in range(count):
        a = rng.uniform(0, 2 * math.pi)
        rad = rng.uniform(0.25, 0.92) * r
        x0 = cx + rad * math.cos(a)
        y0 = cy + rad * math.sin(a)
        length = rng.uniform(*length_range)
        items.append(line(x0, y0, x0 + math.cos(a) * length, y0 + math.sin(a) * length,
                           color, 1.6, rng.uniform(*opacity_range)))
    return "".join(items)


def bokeh_backdrop(rng, colors, blur_id, n=12, r_range=(90, 300), opacity_range=(0.12, 0.3)):
    items = []
    for _ in range(n):
        cx = rng.uniform(-100, W + 100)
        cy = rng.uniform(-100, H + 100)
        r = rng.uniform(*r_range)
        items.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{rng.choice(colors)}" '
                     f'opacity="{rng.uniform(*opacity_range):.2f}" filter="url(#{blur_id})"/>')
    return items


def realistic_scene(motif_fn, palette, sky, count=5, size_range=(220, 340),
                     texture_color=None, texture_count=24, blur_std=14, angle=100):
    """Factory mirroring `scene()`, but composing the bokeh/shadow/texture/
    highlight/vignette stack around each `motif_fn(cx, cy, size, rotation,
    opacity)` instance for a "realistic style" background."""
    def build(svg, rng):
        grad_bg(svg, sky, angle)
        blur_id = svg.blur_filter(blur_std)
        for item in bokeh_backdrop(rng, palette, blur_id):
            svg.add(item)
        for _ in range(count):
            cx = rng.uniform(180, W - 180)
            cy = rng.uniform(240, H - 240)
            s = rng.uniform(*size_range)
            rot = rng.uniform(0, 360)
            op = rng.uniform(0.94, 1.0)
            svg.add(shadow_ellipse(cx, cy + s * 0.42, s * 0.34, s * 0.12, blur_id, 0.28))
            svg.add(motif_fn(cx, cy, s, rot, op))
            if texture_color:
                svg.add(fur_texture(cx, cy, s * 0.5, texture_color, texture_count, rng))
            svg.add(glow_highlight(svg, cx - s * 0.22, cy - s * 0.28, s * 0.38, 0.32))
        svg.add(vignette(svg, 0.2))
    return build


# --------------------------------------------------------------------------
# Category definitions
# --------------------------------------------------------------------------
# Each category: slug, name, list of 6 (title, builder_fn) pairs.
# Builder receives (svg, rng) and paints the full scene.

def grad_bg(svg, colors, angle=135):
    background_rect(svg, svg.linear_gradient(colors, angle))


CATS = []
CATS_BY_SLUG = {}


def cat(slug, name, variants, style="illustrated"):
    """Register (title, builder_fn) variants under `slug`. Calling this again
    with a slug already used appends to that category's variant list instead
    of creating a duplicate tab -- used to layer a second `style` (e.g.
    "realistic") of artwork into an existing category."""
    entry = CATS_BY_SLUG.get(slug)
    if entry is None:
        entry = {"slug": slug, "name": name, "variants": []}
        CATS.append(entry)
        CATS_BY_SLUG[slug] = entry
    for title, builder in variants:
        entry["variants"].append((title, builder, style))


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


# ============================================================================
# EXPANSION PACK -- 15 more categories, 20 variants each (300 backgrounds).
# Includes a dedicated Huskies category (kids love huskies!) alongside 14
# other fresh themes, so the new set isn't "all huskies."
# ============================================================================

def scene(motif_fn, sky, count=7, size_range=(150, 260), rotate=False, angle=100):
    """Generic gradient-background + scatter-of-one-motif scene factory,
    used throughout the expansion pack to keep each category's code small."""
    def build(svg, rng):
        grad_bg(svg, sky, angle)
        scatter(svg, rng, motif_fn, count, size_range=size_range, rotate=rotate)
    return build


# ---- Husky shape -----------------------------------------------------------

def husky_face_shape(cx, cy, size, coat, coat_light, eye1, eye2, opacity=1, style="face"):
    s = size / 100.0
    items = []
    # pointed ears
    items.append(polygon([(cx-62*s, cy-38*s), (cx-30*s, cy-38*s), (cx-48*s, cy-100*s)], coat, opacity))
    items.append(polygon([(cx+62*s, cy-38*s), (cx+30*s, cy-38*s), (cx+48*s, cy-100*s)], coat, opacity))
    items.append(polygon([(cx-54*s, cy-42*s), (cx-38*s, cy-42*s), (cx-46*s, cy-80*s)], "#2b2b2b", opacity * 0.5))
    items.append(polygon([(cx+54*s, cy-42*s), (cx+38*s, cy-42*s), (cx+46*s, cy-80*s)], "#2b2b2b", opacity * 0.5))
    # head + light face mask
    items.append(circle(cx, cy, 65 * s, coat, opacity))
    items.append(path(
        f"M {cx-40*s} {cy+10*s} C {cx-40*s} {cy-30*s}, {cx-18*s} {cy-45*s}, {cx} {cy-45*s} "
        f"C {cx+18*s} {cy-45*s}, {cx+40*s} {cy-30*s}, {cx+40*s} {cy+10*s} "
        f"C {cx+40*s} {cy+45*s}, {cx+20*s} {cy+60*s}, {cx} {cy+60*s} "
        f"C {cx-20*s} {cy+60*s}, {cx-40*s} {cy+45*s}, {cx-40*s} {cy+10*s} Z",
        coat_light, opacity))
    # eyes (support heterochromia via eye1 != eye2)
    items.append(ellipse(cx - 22 * s, cy - 8 * s, 11 * s, 13 * s, eye1, opacity))
    items.append(ellipse(cx + 22 * s, cy - 8 * s, 11 * s, 13 * s, eye2, opacity))
    items.append(circle(cx - 22 * s, cy - 8 * s, 4 * s, "#111", opacity))
    items.append(circle(cx + 22 * s, cy - 8 * s, 4 * s, "#111", opacity))
    # nose + mouth
    items.append(ellipse(cx, cy + 18 * s, 11 * s, 8 * s, "#1a1a1a", opacity))
    if style == "howl":
        items.append(ellipse(cx, cy + 42 * s, 14 * s, 20 * s, "#5c2a2a", opacity))
        items.append(ellipse(cx, cy + 48 * s, 8 * s, 10 * s, "#ff8fa3", opacity))
    else:
        items.append(f'<path d="M {cx-14*s} {cy+26*s} Q {cx} {cy+36*s} {cx+14*s} {cy+26*s}" '
                     f'fill="none" stroke="#1a1a1a" stroke-width="{3*s:.1f}" stroke-linecap="round" '
                     f'opacity="{opacity:.2f}"/>')
    if style == "puppy":
        items.append(circle(cx - 34 * s, cy + 40 * s, 8 * s, coat_light, opacity * 0.9))
        items.append(circle(cx + 34 * s, cy + 40 * s, 8 * s, coat_light, opacity * 0.9))
    return group(items)


def husky_sled_shape(cx, cy, size, coat, coat_light, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 70 * s, cy + 30 * s, 140 * s, 22 * s, "#8a5a2b", rx=6 * s, opacity=opacity),
        rect(cx - 70 * s, cy + 52 * s, 140 * s, 10 * s, "#5b3a1f", rx=4 * s, opacity=opacity),
    ]
    for i, dx in enumerate([-140, -60, 20]):
        fs = size * 0.42
        items.append(husky_face_shape(cx + dx * s, cy - 20 * s, fs, coat, coat_light, "#7ec8e3", "#7ec8e3",
                                       opacity, "face"))
    return group(items)


HUSKY_COATS = [
    ("#8a8f99", "#f4f4f4", "Classic Grey & White"),
    ("#2b2b2b", "#ffffff", "Black & White"),
    ("#b5651d", "#fbe8d3", "Copper & Cream"),
    ("#f4f4f4", "#ffffff", "Pure Snow White"),
    ("#c9b18a", "#f7efe0", "Agouti Sable"),
    ("#7a7f87", "#e8e8ea", "Silver Storm"),
]
HUSKY_EYES = [("#7ec8e3", "#7ec8e3"), ("#6b4423", "#6b4423"), ("#7ec8e3", "#6b4423")]


def husky_scene(coat, coat_light, eyes, sky, style="face", team=False, angle=100):
    def build(svg, rng):
        grad_bg(svg, sky, angle)
        if team:
            scatter(svg, rng, lambda cx, cy, s, r, o: husky_sled_shape(cx, cy, s, coat, coat_light, o), 2,
                    size_range=(260, 340))
        else:
            scatter(svg, rng, lambda cx, cy, s, r, o: husky_face_shape(cx, cy, s, coat, coat_light,
                    eyes[0], eyes[1], o, style), 5, size_range=(230, 340))
    return build


cat("huskies", "Huskies", [
    ("Classic Grey Husky", husky_scene("#8a8f99", "#f4f4f4", ("#7ec8e3", "#7ec8e3"), ["#dbe9ff", "#a8c6ff"])),
    ("Black & White Husky", husky_scene("#2b2b2b", "#ffffff", ("#6b4423", "#6b4423"), ["#eef2f7", "#d6e0ea"])),
    ("Copper Husky Charm", husky_scene("#b5651d", "#fbe8d3", ("#7ec8e3", "#7ec8e3"), ["#fff3e0", "#ffe0c2"])),
    ("Snow White Husky", husky_scene("#f4f4f4", "#ffffff", ("#7ec8e3", "#6b4423"), ["#eaf6ff", "#d6efff"])),
    ("Agouti Sable Husky", husky_scene("#c9b18a", "#f7efe0", ("#6b4423", "#6b4423"), ["#f0ead2", "#e4d9b8"])),
    ("Silver Storm Husky", husky_scene("#7a7f87", "#e8e8ea", ("#7ec8e3", "#7ec8e3"), ["#c9d6e8", "#9fb4cc"])),
    ("Heterochromia Husky", husky_scene("#8a8f99", "#f4f4f4", ("#7ec8e3", "#6b4423"), ["#fdf0ff", "#eae0ff"])),
    ("Husky Howling at the Moon", husky_scene("#2b2b2b", "#ffffff", ("#7ec8e3", "#7ec8e3"),
                                               ["#0d1b4c", "#1a1a40"], style="howl")),
    ("Playful Husky Puppy", husky_scene("#8a8f99", "#fdf6ec", ("#6b4423", "#6b4423"),
                                         ["#fff3e0", "#ffe4c2"], style="puppy")),
    ("Husky in the Snowstorm", husky_scene("#f4f4f4", "#e8e8ea", ("#7ec8e3", "#7ec8e3"), ["#cfe8ff", "#eaf6ff"])),
    ("Aurora Husky Night", husky_scene("#7a7f87", "#e8e8ea", ("#7ec8e3", "#6b4423"), ["#0f2027", "#2c5364"])),
    ("Husky Sunset Silhouette", husky_scene("#b5651d", "#fbe8d3", ("#6b4423", "#6b4423"),
                                             ["#ff9f7b", "#ff6f91"])),
    ("Rainbow Husky Squad", husky_scene("#2b2b2b", "#ffffff", ("#7ec8e3", "#7ec8e3"),
                                         ["#ff9fbf", "#9fd8ff", "#c2f0c2"])),
    ("Cozy Cabin Husky", husky_scene("#8a8f99", "#f4f4f4", ("#6b4423", "#6b4423"), ["#fff0e0", "#ffdca8"])),
    ("Husky Pack in the Pines", husky_scene("#c9b18a", "#f7efe0", ("#7ec8e3", "#7ec8e3"), ["#d8f3dc", "#b7e4c7"])),
    ("Husky Sled Team Adventure", husky_scene("#8a8f99", "#f4f4f4", ("#7ec8e3", "#7ec8e3"),
                                               ["#cfe8ff", "#eaf6ff"], team=True)),
    ("Midnight Husky Pack", husky_scene("#2b2b2b", "#ffffff", ("#7ec8e3", "#7ec8e3"), ["#03071e", "#0a2540"])),
    ("Golden Hour Husky", husky_scene("#b5651d", "#fbe8d3", ("#7ec8e3", "#6b4423"), ["#ffe8b0", "#ffcf8a"])),
    ("Husky in a Bandana", husky_scene("#7a7f87", "#e8e8ea", ("#6b4423", "#6b4423"), ["#ffe0ec", "#ffc2d9"])),
    ("Frosty Husky Meadow", husky_scene("#f4f4f4", "#e8e8ea", ("#7ec8e3", "#7ec8e3"), ["#eafff1", "#d0f4de"])),
])


# ---- Arctic & Polar Animals --------------------------------------------------

def penguin_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        ellipse(cx, cy, 45 * s, 65 * s, "#1a1a1a", opacity),
        ellipse(cx, cy + 8 * s, 30 * s, 50 * s, "#ffffff", opacity),
        polygon([(cx-10*s, cy-45*s), (cx+10*s, cy-45*s), (cx, cy-60*s)], "#f4a261", opacity),
        circle(cx - 12 * s, cy - 40 * s, 5 * s, "#1a1a1a", opacity),
        circle(cx + 12 * s, cy - 40 * s, 5 * s, "#1a1a1a", opacity),
        ellipse(cx - 40 * s, cy + 10 * s, 12 * s, 30 * s, "#1a1a1a", opacity, transform=f"rotate(-20 {cx-40*s} {cy+10*s})"),
        ellipse(cx + 40 * s, cy + 10 * s, 12 * s, 30 * s, "#1a1a1a", opacity, transform=f"rotate(20 {cx+40*s} {cy+10*s})"),
        polygon([(cx-14*s, cy+58*s), (cx+14*s, cy+58*s), (cx, cy+72*s)], "#f4a261", opacity),
    ]
    return group(items)


def polar_bear_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        circle(cx - 48 * s, cy - 48 * s, 18 * s, "#fdfdfd", opacity),
        circle(cx + 48 * s, cy - 48 * s, 18 * s, "#fdfdfd", opacity),
        circle(cx, cy, 65 * s, "#fdfdfd", opacity),
        ellipse(cx, cy + 22 * s, 28 * s, 20 * s, "#f4f1ea", opacity),
        circle(cx - 22 * s, cy - 8 * s, 7 * s, "#1a1a1a", opacity),
        circle(cx + 22 * s, cy - 8 * s, 7 * s, "#1a1a1a", opacity),
        ellipse(cx, cy + 20 * s, 9 * s, 6 * s, "#1a1a1a", opacity),
    ]
    return group(items)


def seal_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        ellipse(cx, cy, 60 * s, 38 * s, fill, opacity),
        ellipse(cx - 66 * s, cy + 14 * s, 16 * s, 8 * s, fill, opacity, transform=f"rotate(-30 {cx-66*s} {cy+14*s})"),
        circle(cx + 40 * s, cy - 6 * s, 5 * s, "#1a1a1a", opacity),
        ellipse(cx + 55 * s, cy + 4 * s, 6 * s, 4 * s, "#1a1a1a", opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def walrus_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        ellipse(cx, cy, 60 * s, 45 * s, "#b98d6f", opacity),
        circle(cx - 20 * s, cy - 10 * s, 6 * s, "#1a1a1a", opacity),
        circle(cx + 20 * s, cy - 10 * s, 6 * s, "#1a1a1a", opacity),
        polygon([(cx-16*s, cy+15*s), (cx-10*s, cy+55*s), (cx-2*s, cy+15*s)], "#f4f1ea", opacity),
        polygon([(cx+16*s, cy+15*s), (cx+10*s, cy+55*s), (cx+2*s, cy+15*s)], "#f4f1ea", opacity),
    ]
    return group(items)


def owl_shape(cx, cy, size, body_color, belly_color, eye_color, opacity=1):
    s = size / 100.0
    items = [
        polygon([(cx-55*s, cy-70*s), (cx-30*s, cy-70*s), (cx-42*s, cy-100*s)], body_color, opacity),
        polygon([(cx+55*s, cy-70*s), (cx+30*s, cy-70*s), (cx+42*s, cy-100*s)], body_color, opacity),
        ellipse(cx, cy, 60 * s, 70 * s, body_color, opacity),
        ellipse(cx, cy + 15 * s, 34 * s, 45 * s, belly_color, opacity),
        circle(cx - 22 * s, cy - 15 * s, 18 * s, "#ffffff", opacity),
        circle(cx + 22 * s, cy - 15 * s, 18 * s, "#ffffff", opacity),
        circle(cx - 22 * s, cy - 15 * s, 9 * s, eye_color, opacity),
        circle(cx + 22 * s, cy - 15 * s, 9 * s, eye_color, opacity),
        circle(cx - 22 * s, cy - 15 * s, 4 * s, "#1a1a1a", opacity),
        circle(cx + 22 * s, cy - 15 * s, 4 * s, "#1a1a1a", opacity),
        polygon([(cx-6*s, cy+2*s), (cx+6*s, cy+2*s), (cx, cy+16*s)], "#f4a261", opacity),
    ]
    return group(items)


cat("arctic-polar", "Arctic & Polar Animals", [
    ("Waddling Penguins", scene(lambda cx, cy, s, r, o: penguin_shape(cx, cy, s, o), ["#a8dadc", "#457b9d"], 7)),
    ("Polar Bear Playground", scene(lambda cx, cy, s, r, o: polar_bear_shape(cx, cy, s, o), ["#eaf6ff", "#cdeffd"], 5, (220, 320))),
    ("Seal Pup Splash", scene(lambda cx, cy, s, r, o: seal_shape(cx, cy, s, "#8d99ae", o, r), ["#0077b6", "#00b4d8"], 6, (140, 220), True)),
    ("Walrus Waters", scene(lambda cx, cy, s, r, o: walrus_shape(cx, cy, s, o), ["#8ecae6", "#219ebc"], 5, (200, 280))),
    ("Snowy Owl Night", scene(lambda cx, cy, s, r, o: owl_shape(cx, cy, s, "#f4f4f4", "#e8e8ea", "#f4a261", o), ["#0d1b4c", "#1a1a40"], 5, (180, 260))),
    ("Arctic Fox Frost", scene(lambda cx, cy, s, r, o: animal_face_shape(cx, cy, s, "#ffffff", "#e8e8ea", "fox", o), ["#eaf6ff", "#d6efff"], 5, (200, 300))),
    ("Iceberg Penguin Party", scene(lambda cx, cy, s, r, o: penguin_shape(cx, cy, s, o), ["#caf0f8", "#90e0ef"], 8, (110, 190))),
    ("Aurora Polar Bears", scene(lambda cx, cy, s, r, o: polar_bear_shape(cx, cy, s, o), ["#0f2027", "#2c5364"], 4, (220, 320))),
    ("Snowflakes & Seals", scene(lambda cx, cy, s, r, o: seal_shape(cx, cy, s, "#adb5bd", o, r), ["#dbe9ff", "#a8c6ff"], 6, (130, 210), True)),
    ("Frozen Tundra Walrus", scene(lambda cx, cy, s, r, o: walrus_shape(cx, cy, s, o), ["#e0f7fa", "#b2ebf2"], 5, (190, 270))),
    ("Snowy Owl Daytime", scene(lambda cx, cy, s, r, o: owl_shape(cx, cy, s, "#e8e8ea", "#ffffff", "#f4a261", o), ["#eaf6ff", "#cdeffd"], 5, (180, 260))),
    ("Penguin Ice Slide", scene(lambda cx, cy, s, r, o: penguin_shape(cx, cy, s, o), ["#ade8f4", "#48cae4"], 6, (150, 230))),
    ("Polar Night Sky", scene(lambda cx, cy, s, r, o: polar_bear_shape(cx, cy, s, o), ["#020024", "#090979"], 4, (220, 320))),
    ("Baby Seal Snuggles", scene(lambda cx, cy, s, r, o: seal_shape(cx, cy, s, "#f4f1ea", o, r), ["#fff8e0", "#ffefc2"], 5, (150, 230), True)),
    ("Glacier Blue Walrus", scene(lambda cx, cy, s, r, o: walrus_shape(cx, cy, s, o), ["#03045e", "#0077b6"], 5, (190, 270))),
    ("Frosty Fox & Friends", scene(lambda cx, cy, s, r, o: animal_face_shape(cx, cy, s, "#f4f4f4", "#ffd6ec", "fox", o), ["#f3e8ff", "#e0d4ff"], 5, (200, 300))),
    ("Icy Owl Eyes", scene(lambda cx, cy, s, r, o: owl_shape(cx, cy, s, "#8ecae6", "#eaf6ff", "#ffd166", o), ["#023e8a", "#0096c7"], 5, (180, 260))),
    ("Penguin Family Portrait", scene(lambda cx, cy, s, r, o: penguin_shape(cx, cy, s, o), ["#fff8e0", "#ffefc2"], 6, (160, 240))),
    ("Snowdrift Polar Bears", scene(lambda cx, cy, s, r, o: polar_bear_shape(cx, cy, s, o), ["#f8f9fa", "#dee2e6"], 5, (220, 320))),
    ("Twilight Arctic Waters", scene(lambda cx, cy, s, r, o: seal_shape(cx, cy, s, "#6c757d", o, r), ["#3a0ca3", "#7209b7"], 6, (140, 220), True)),
])


# ---- Farm & Barnyard ---------------------------------------------------------

def cow_shape(cx, cy, size, base_color, spot_color, opacity=1):
    s = size / 100.0
    items = [
        circle(cx, cy, 62 * s, base_color, opacity),
        circle(cx - 25 * s, cy - 20 * s, 16 * s, spot_color, opacity),
        circle(cx + 28 * s, cy + 15 * s, 14 * s, spot_color, opacity),
        ellipse(cx - 50 * s, cy - 45 * s, 14 * s, 20 * s, base_color, opacity),
        ellipse(cx + 50 * s, cy - 45 * s, 14 * s, 20 * s, base_color, opacity),
        ellipse(cx, cy + 20 * s, 30 * s, 22 * s, "#ffe8f0", opacity),
        circle(cx - 22 * s, cy - 8 * s, 8 * s, "#1a1a1a", opacity),
        circle(cx + 22 * s, cy - 8 * s, 8 * s, "#1a1a1a", opacity),
        circle(cx - 12 * s, cy + 18 * s, 4 * s, "#c96a80", opacity),
        circle(cx + 12 * s, cy + 18 * s, 4 * s, "#c96a80", opacity),
    ]
    return group(items)


def pig_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        circle(cx, cy, 60 * s, "#ffafc5", opacity),
        ellipse(cx - 45 * s, cy - 45 * s, 14 * s, 16 * s, "#ffafc5", opacity),
        ellipse(cx + 45 * s, cy - 45 * s, 14 * s, 16 * s, "#ffafc5", opacity),
        ellipse(cx, cy + 15 * s, 22 * s, 16 * s, "#ff8fa3", opacity),
        circle(cx - 8 * s, cy + 15 * s, 4 * s, "#c96a80", opacity),
        circle(cx + 8 * s, cy + 15 * s, 4 * s, "#c96a80", opacity),
        circle(cx - 20 * s, cy - 8 * s, 6 * s, "#1a1a1a", opacity),
        circle(cx + 20 * s, cy - 8 * s, 6 * s, "#1a1a1a", opacity),
    ]
    return group(items)


def chicken_shape(cx, cy, size, body_color, opacity=1):
    s = size / 100.0
    items = [
        circle(cx, cy + 5 * s, 48 * s, body_color, opacity),
        circle(cx + 30 * s, cy - 35 * s, 26 * s, body_color, opacity),
        polygon([(cx+50*s, cy-38*s), (cx+50*s, cy-24*s), (cx+66*s, cy-31*s)], "#f4a261", opacity),
        polygon([(cx+14*s, cy-58*s), (cx+22*s, cy-58*s), (cx+18*s, cy-70*s)], "#e63946", opacity),
        polygon([(cx+24*s, cy-56*s), (cx+32*s, cy-56*s), (cx+28*s, cy-70*s)], "#e63946", opacity),
        circle(cx + 34 * s, cy - 38 * s, 4 * s, "#1a1a1a", opacity),
    ]
    return group(items)


def barn_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 80 * s, cy - 10 * s, 160 * s, 100 * s, "#e63946", opacity=opacity),
        polygon([(cx-95*s, cy-10*s), (cx+95*s, cy-10*s), (cx, cy-80*s)], "#6b4423", opacity),
        rect(cx - 20 * s, cy + 30 * s, 40 * s, 60 * s, "#f4f1ea", rx=6 * s, opacity=opacity),
        polygon([(cx-15*s, cy-70*s), (cx+15*s, cy-70*s), (cx, cy-95*s)], "#f4f1ea", opacity),
    ]
    return group(items)


def sheep_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [cloud_shape(cx, cy, size * 0.9, "#f8f9fa", opacity)]
    items.append(circle(cx - size * 0.75, cy + size * 0.02, size * 0.22, "#4a4a4a", opacity))
    items.append(circle(cx - size * 0.82, cy - size * 0.05, 4 * (size / 100), "#1a1a1a", opacity))
    for dx in (-0.4, 0, 0.5):
        items.append(rect(cx + dx * size, cy + size * 0.28, size * 0.08, size * 0.22, "#4a4a4a", rx=3, opacity=opacity))
    return group(items)


cat("farm-barnyard", "Farm & Barnyard", [
    ("Spotted Cow Meadow", scene(lambda cx, cy, s, r, o: cow_shape(cx, cy, s, "#f8f9fa", "#2b2b2b", o), ["#cdeac0", "#eaf7d0"], 6, (180, 260))),
    ("Pink Piggy Patch", scene(lambda cx, cy, s, r, o: pig_shape(cx, cy, s, o), ["#fff0f5", "#ffe6ee"], 7, (160, 240))),
    ("Rooster Morning Call", scene(lambda cx, cy, s, r, o: chicken_shape(cx, cy, s, "#fff3e0", o), ["#ffe066", "#ffd166"], 8, (140, 220))),
    ("Red Barn Sunrise", scene(lambda cx, cy, s, r, o: barn_shape(cx, cy, s, o), ["#ffe8b0", "#ffcf8a"], 4, (260, 380))),
    ("Fluffy Sheep Field", scene(lambda cx, cy, s, r, o: sheep_shape(cx, cy, s, o), ["#eaf7ff", "#dff3ff"], 8, (140, 220))),
    ("Brown & White Cows", scene(lambda cx, cy, s, r, o: cow_shape(cx, cy, s, "#fdf6ec", "#b5651d", o), ["#d8f3dc", "#b7e4c7"], 6, (180, 260))),
    ("Barnyard Chicken Coop", scene(lambda cx, cy, s, r, o: chicken_shape(cx, cy, s, "#f4a261", o), ["#fff8e0", "#ffe9c2"], 7, (140, 220))),
    ("Golden Hay Barn", scene(lambda cx, cy, s, r, o: barn_shape(cx, cy, s, o), ["#fff3e0", "#ffe4c2"], 4, (260, 380))),
    ("Piglet Playtime", scene(lambda cx, cy, s, r, o: pig_shape(cx, cy, s, o), ["#ffe0ec", "#ffc2d9"], 7, (150, 230))),
    ("Woolly Sheep Sunset", scene(lambda cx, cy, s, r, o: sheep_shape(cx, cy, s, o), ["#ff9f7b", "#ff6f91"], 6, (150, 230))),
    ("Farmyard Friends Mix", scene(lambda cx, cy, s, r, o: pig_shape(cx, cy, s, o), ["#f1faee", "#dff7e0"], 5, (160, 240))),
    ("Black & White Dairy Cows", scene(lambda cx, cy, s, r, o: cow_shape(cx, cy, s, "#ffffff", "#1a1a1a", o), ["#eaf6ff", "#cdeffd"], 6, (180, 260))),
    ("Chicken & Sunflowers", scene(lambda cx, cy, s, r, o: chicken_shape(cx, cy, s, "#ffd166", o), ["#eafff1", "#d0f4de"], 7, (140, 220))),
    ("Countryside Red Barn", scene(lambda cx, cy, s, r, o: barn_shape(cx, cy, s, o), ["#a8dadc", "#457b9d"], 4, (260, 380))),
    ("Spring Lamb Meadow", scene(lambda cx, cy, s, r, o: sheep_shape(cx, cy, s, o), ["#f0ead2", "#e4d9b8"], 8, (130, 210))),
    ("Sunny Piglet Pasture", scene(lambda cx, cy, s, r, o: pig_shape(cx, cy, s, o), ["#fff3b0", "#ffe066"], 7, (150, 230))),
    ("Grazing Cow Hillside", scene(lambda cx, cy, s, r, o: cow_shape(cx, cy, s, "#f8f9fa", "#6b4423", o), ["#e0f7fa", "#b2ebf2"], 5, (190, 270))),
    ("Rise & Shine Rooster", scene(lambda cx, cy, s, r, o: chicken_shape(cx, cy, s, "#e76f51", o), ["#ffcf8a", "#ff9f7b"], 7, (150, 230))),
    ("Wooly Sheep Cloud Field", scene(lambda cx, cy, s, r, o: sheep_shape(cx, cy, s, o), ["#dbe9ff", "#a8c6ff"], 8, (130, 210))),
    ("Barnyard Blue Sky", scene(lambda cx, cy, s, r, o: barn_shape(cx, cy, s, o), ["#8ecae6", "#219ebc"], 4, (260, 380))),
])


# ---- Ocean & Sea Life ---------------------------------------------------------

def whale_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        path(f"M {cx-70*s} {cy} C {cx-70*s} {cy-40*s}, {cx-20*s} {cy-55*s}, {cx+30*s} {cy-45*s} "
             f"C {cx+65*s} {cy-38*s}, {cx+80*s} {cy-10*s}, {cx+70*s} {cy+15*s} "
             f"C {cx+40*s} {cy+35*s}, {cx-40*s} {cy+35*s}, {cx-70*s} {cy} Z", fill, opacity),
        polygon([(cx-70*s, cy), (cx-100*s, cy-20*s), (cx-100*s, cy+10*s)], fill, opacity),
        circle(cx + 40 * s, cy - 25 * s, 4 * s, "#1a1a1a", opacity),
        f'<path d="M {cx-10*s:.1f} {cy-55*s:.1f} Q {cx:.1f} {cy-78*s:.1f} {cx+10*s:.1f} {cy-55*s:.1f}" '
        f'fill="none" stroke="#a6e3ff" stroke-width="{6*s:.1f}" opacity="{opacity*0.7:.2f}"/>',
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def octopus_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [circle(cx, cy - 10 * s, 50 * s, fill, opacity)]
    for i in range(6):
        x0 = cx - 45 * s + i * 18 * s
        items.append(f'<path d="M {x0:.1f} {cy+20*s:.1f} Q {x0-10*s:.1f} {cy+60*s:.1f} {x0+8*s:.1f} {cy+80*s:.1f}" '
                     f'fill="none" stroke="{fill}" stroke-width="{14*s:.1f}" stroke-linecap="round" '
                     f'opacity="{opacity:.2f}"/>')
    items.append(circle(cx - 18 * s, cy - 15 * s, 8 * s, "#ffffff", opacity))
    items.append(circle(cx + 18 * s, cy - 15 * s, 8 * s, "#ffffff", opacity))
    items.append(circle(cx - 18 * s, cy - 15 * s, 4 * s, "#1a1a1a", opacity))
    items.append(circle(cx + 18 * s, cy - 15 * s, 4 * s, "#1a1a1a", opacity))
    return group(items)


def sea_turtle_shape(cx, cy, size, shell_color, body_color, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        ellipse(cx, cy, 55 * s, 42 * s, shell_color, opacity),
        circle(cx - 15 * s, cy - 12 * s, 8 * s, shell_color, opacity * 0.6),
        circle(cx + 15 * s, cy - 5 * s, 8 * s, shell_color, opacity * 0.6),
        circle(cx, cy + 15 * s, 8 * s, shell_color, opacity * 0.6),
        ellipse(cx - 68 * s, cy, 20 * s, 12 * s, body_color, opacity),
        ellipse(cx - 30 * s, cy + 40 * s, 16 * s, 10 * s, body_color, opacity, transform=f"rotate(30 {cx-30*s} {cy+40*s})"),
        ellipse(cx + 30 * s, cy + 40 * s, 16 * s, 10 * s, body_color, opacity, transform=f"rotate(-30 {cx+30*s} {cy+40*s})"),
        ellipse(cx - 30 * s, cy - 38 * s, 16 * s, 10 * s, body_color, opacity, transform=f"rotate(-30 {cx-30*s} {cy-38*s})"),
        ellipse(cx + 30 * s, cy - 38 * s, 16 * s, 10 * s, body_color, opacity, transform=f"rotate(30 {cx+30*s} {cy-38*s})"),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def jellyfish_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [f'<path d="M {cx-45*s:.1f} {cy:.1f} A {45*s:.1f} {40*s:.1f} 0 0 1 {cx+45*s:.1f} {cy:.1f} '
              f'Q {cx+45*s:.1f} {cy+18*s:.1f} {cx+30*s:.1f} {cy+12*s:.1f} '
              f'Q {cx+15*s:.1f} {cy+22*s:.1f} {cx:.1f} {cy+12*s:.1f} '
              f'Q {cx-15*s:.1f} {cy+22*s:.1f} {cx-30*s:.1f} {cy+12*s:.1f} '
              f'Q {cx-45*s:.1f} {cy+18*s:.1f} {cx-45*s:.1f} {cy:.1f} Z" fill="{fill}" opacity="{opacity:.2f}"/>']
    for dx in (-25, -8, 8, 25):
        items.append(line(cx + dx * s, cy + 15 * s, cx + dx * s * 1.3, cy + 55 * s, fill, 5 * s, opacity * 0.8))
    return group(items)


def dolphin_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        path(f"M {cx-60*s} {cy+10*s} C {cx-40*s} {cy-40*s}, {cx+20*s} {cy-40*s}, {cx+65*s} {cy-5*s} "
             f"C {cx+40*s} {cy+15*s}, {cx-20*s} {cy+30*s}, {cx-60*s} {cy+10*s} Z", fill, opacity),
        polygon([(cx-20*s, cy-35*s), (cx-5*s, cy-60*s), (cx+5*s, cy-32*s)], fill, opacity),
        polygon([(cx+55*s, cy-8*s), (cx+80*s, cy-25*s), (cx+80*s, cy+2*s)], fill, opacity),
        circle(cx - 45 * s, cy - 5 * s, 4 * s, "#1a1a1a", opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("ocean-sea-life", "Ocean & Sea Life", [
    ("Gentle Giant Whale", scene(lambda cx, cy, s, r, o: whale_shape(cx, cy, s, "#4361ee", o, r), ["#03045e", "#0077b6"], 5, (200, 300), True)),
    ("Curious Octopus", scene(lambda cx, cy, s, r, o: octopus_shape(cx, cy, s, "#f15bb5", o), ["#023e8a", "#0096c7"], 6, (150, 230))),
    ("Sea Turtle Voyage", scene(lambda cx, cy, s, r, o: sea_turtle_shape(cx, cy, s, "#2d6a4f", "#52b788", o, r), ["#00b4d8", "#90e0ef"], 6, (160, 240), True)),
    ("Jellyfish Glow", scene(lambda cx, cy, s, r, o: jellyfish_shape(cx, cy, s, "#c8b6ff", o), ["#03045e", "#0a4d68"], 7, (140, 220))),
    ("Playful Dolphins", scene(lambda cx, cy, s, r, o: dolphin_shape(cx, cy, s, "#4cc9f0", o, r), ["#ade8f4", "#48cae4"], 6, (170, 250), True)),
    ("Deep Blue Whale Song", scene(lambda cx, cy, s, r, o: whale_shape(cx, cy, s, "#5390d9", o, r), ["#001d3d", "#003566"], 4, (220, 320), True)),
    ("Orange Octopus Garden", scene(lambda cx, cy, s, r, o: octopus_shape(cx, cy, s, "#ff9f1c", o), ["#0077b6", "#00b4d8"], 6, (150, 230))),
    ("Coral Reef Turtles", scene(lambda cx, cy, s, r, o: sea_turtle_shape(cx, cy, s, "#e76f51", "#f4a261", o, r), ["#0096c7", "#48cae4"], 6, (160, 240), True)),
    ("Pink Jellyfish Drift", scene(lambda cx, cy, s, r, o: jellyfish_shape(cx, cy, s, "#ff9fd6", o), ["#0a4d68", "#088395"], 7, (140, 220))),
    ("Sunny Dolphin Splash", scene(lambda cx, cy, s, r, o: dolphin_shape(cx, cy, s, "#00b4d8", o, r), ["#a8e6ff", "#dff7ff"], 6, (170, 250), True)),
    ("Purple Whale Dreams", scene(lambda cx, cy, s, r, o: whale_shape(cx, cy, s, "#9b5de5", o, r), ["#240046", "#3c096c"], 4, (220, 320), True)),
    ("Teal Octopus Depths", scene(lambda cx, cy, s, r, o: octopus_shape(cx, cy, s, "#2ec4b6", o), ["#03045e", "#023e8a"], 6, (150, 230))),
    ("Golden Sea Turtle", scene(lambda cx, cy, s, r, o: sea_turtle_shape(cx, cy, s, "#ffb703", "#ffd166", o, r), ["#023047", "#219ebc"], 6, (160, 240), True)),
    ("Yellow Jellyfish Bloom", scene(lambda cx, cy, s, r, o: jellyfish_shape(cx, cy, s, "#ffe066", o), ["#001d3d", "#003566"], 7, (140, 220))),
    ("Dolphin Sunset Leap", scene(lambda cx, cy, s, r, o: dolphin_shape(cx, cy, s, "#f4a261", o, r), ["#ff9f7b", "#ff6f91"], 6, (170, 250), True)),
    ("Whale & Bubbles", scene(lambda cx, cy, s, r, o: whale_shape(cx, cy, s, "#48cae4", o, r), ["#caf0f8", "#ade8f4"], 5, (200, 300), True)),
    ("Rainbow Reef Octopus", scene(lambda cx, cy, s, r, o: octopus_shape(cx, cy, s, "#06d6a0", o), ["#ff9fbf", "#9fd8ff"], 6, (150, 230))),
    ("Emerald Sea Turtle", scene(lambda cx, cy, s, r, o: sea_turtle_shape(cx, cy, s, "#118ab2", "#06d6a0", o, r), ["#d8f3dc", "#b7e4c7"], 6, (160, 240), True)),
    ("Moonlit Jellyfish", scene(lambda cx, cy, s, r, o: jellyfish_shape(cx, cy, s, "#a6e3ff", o), ["#0d1b4c", "#1a1a40"], 7, (140, 220))),
    ("Dolphin Pod Parade", scene(lambda cx, cy, s, r, o: dolphin_shape(cx, cy, s, "#4361ee", o, r), ["#0077b6", "#00b4d8"], 7, (150, 230), True)),
])


# ---- Birds & Feathers -----------------------------------------------------------

def parrot_shape(cx, cy, size, body_color, wing_color, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        ellipse(cx, cy, 40 * s, 55 * s, body_color, opacity),
        ellipse(cx + 10 * s, cy + 5 * s, 20 * s, 32 * s, wing_color, opacity),
        circle(cx, cy - 48 * s, 26 * s, body_color, opacity),
        polygon([(cx-10*s, cy-40*s), (cx-30*s, cy-35*s), (cx-8*s, cy-28*s)], "#f4a261", opacity),
        circle(cx + 6 * s, cy - 52 * s, 5 * s, "#1a1a1a", opacity),
        polygon([(cx-10*s, cy+55*s), (cx-16*s, cy+80*s), (cx-4*s, cy+80*s)], "#f4a261", opacity),
        polygon([(cx+10*s, cy+55*s), (cx+4*s, cy+80*s), (cx+16*s, cy+80*s)], "#f4a261", opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def flamingo_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        ellipse(cx, cy - 10 * s, 32 * s, 40 * s, fill, opacity),
        f'<path d="M {cx-25*s:.1f} {cy-30*s:.1f} Q {cx-55*s:.1f} {cy-10*s:.1f} {cx-40*s:.1f} {cy+40*s:.1f}" '
        f'fill="none" stroke="{fill}" stroke-width="{14*s:.1f}" stroke-linecap="round" opacity="{opacity:.2f}"/>',
        circle(cx - 40 * s, cy + 42 * s, 16 * s, fill, opacity),
        polygon([(cx-56*s, cy+38*s), (cx-78*s, cy+46*s), (cx-56*s, cy+50*s)], "#1a1a1a", opacity),
        circle(cx - 44 * s, cy + 38 * s, 3 * s, "#1a1a1a", opacity),
        line(cx, cy + 30 * s, cx - 6 * s, cy + 110 * s, fill, 6 * s, opacity),
        line(cx - 6 * s, cy + 110 * s, cx - 16 * s, cy + 130 * s, fill, 6 * s, opacity),
    ]
    return group(items)


def peacock_shape(cx, cy, size, body_color, tail_colors, opacity=1):
    s = size / 100.0
    items = []
    for i, a in enumerate(range(-70, 71, 20)):
        rad = math.radians(a - 90)
        ex = cx + 90 * s * math.cos(rad)
        ey = cy - 20 * s + 90 * s * math.sin(rad)
        items.append(ellipse(ex, ey, 16 * s, 26 * s, tail_colors[i % len(tail_colors)], opacity * 0.9,
                              transform=f"rotate({a} {ex} {ey})"))
        items.append(circle(ex, ey - 18 * s, 6 * s, tail_colors[(i + 1) % len(tail_colors)], opacity))
    items.append(circle(cx, cy + 20 * s, 26 * s, body_color, opacity))
    items.append(circle(cx, cy - 20 * s, 16 * s, body_color, opacity))
    items.append(circle(cx, cy - 38 * s, 3 * s, tail_colors[0], opacity))
    return group(items)


cat("birds-feathers", "Birds & Feathers", [
    ("Colorful Parrot Perch", scene(lambda cx, cy, s, r, o: parrot_shape(cx, cy, s, "#06d6a0", "#118ab2", o, r), ["#d8f3dc", "#b7e4c7"], 6, (170, 250), True)),
    ("Pretty Pink Flamingos", scene(lambda cx, cy, s, r, o: flamingo_shape(cx, cy, s, "#ff8fa3", o), ["#fff0f5", "#ffe0eb"], 6, (160, 240))),
    ("Majestic Peacock Fan", scene(lambda cx, cy, s, r, o: peacock_shape(cx, cy, s, "#118ab2", ["#06d6a0", "#4cc9f0", "#9b5de5"], o), ["#f3e8ff", "#e0f7ff"], 3, (260, 360))),
    ("Snowy Owl Watch", scene(lambda cx, cy, s, r, o: owl_shape(cx, cy, s, "#f4f4f4", "#e8e8ea", "#ffd166", o), ["#dbe9ff", "#a8c6ff"], 5, (180, 260))),
    ("Rainbow Parrot Jungle", scene(lambda cx, cy, s, r, o: parrot_shape(cx, cy, s, "#ef476f", "#ffd166", o, r), ["#eafff1", "#d0f4de"], 6, (170, 250), True)),
    ("Flamingo Sunset Pond", scene(lambda cx, cy, s, r, o: flamingo_shape(cx, cy, s, "#ff6f91", o), ["#ff9f7b", "#ff6f91"], 6, (160, 240))),
    ("Emerald Peacock Garden", scene(lambda cx, cy, s, r, o: peacock_shape(cx, cy, s, "#2ec4b6", ["#118ab2", "#06d6a0", "#ffd166"], o), ["#eaf6ff", "#cdeffd"], 3, (260, 360))),
    ("Barn Owl Twilight", scene(lambda cx, cy, s, r, o: owl_shape(cx, cy, s, "#c9b18a", "#f7efe0", "#1a1a1a", o), ["#ff9f7b", "#ffcf8a"], 5, (180, 260))),
    ("Blue Parrot Paradise", scene(lambda cx, cy, s, r, o: parrot_shape(cx, cy, s, "#4361ee", "#4cc9f0", o, r), ["#a8e6ff", "#dff7ff"], 6, (170, 250), True)),
    ("Flamingo Flock", scene(lambda cx, cy, s, r, o: flamingo_shape(cx, cy, s, "#f15bb5", o), ["#eaf7ff", "#dff3ff"], 7, (140, 220))),
    ("Purple Peacock Dream", scene(lambda cx, cy, s, r, o: peacock_shape(cx, cy, s, "#7209b7", ["#9b5de5", "#f15bb5", "#4cc9f0"], o), ["#240046", "#3c096c"], 3, (260, 360))),
    ("Golden Owl Eyes", scene(lambda cx, cy, s, r, o: owl_shape(cx, cy, s, "#f4a261", "#ffe8b0", "#1a1a1a", o), ["#fff3e0", "#ffe4c2"], 5, (180, 260))),
    ("Tropical Parrot Duo", scene(lambda cx, cy, s, r, o: parrot_shape(cx, cy, s, "#ffd166", "#ef476f", o, r), ["#caf0f8", "#90e0ef"], 5, (190, 270), True)),
    ("Coral Pink Flamingos", scene(lambda cx, cy, s, r, o: flamingo_shape(cx, cy, s, "#ff9f9f", o), ["#ffe0ec", "#ffc2d9"], 6, (160, 240))),
    ("Sapphire Peacock Feathers", scene(lambda cx, cy, s, r, o: peacock_shape(cx, cy, s, "#023e8a", ["#0096c7", "#48cae4", "#90e0ef"], o), ["#eaf6ff", "#d6efff"], 3, (260, 360))),
    ("Night Owl Stargazing", scene(lambda cx, cy, s, r, o: owl_shape(cx, cy, s, "#3a0ca3", "#c8b6ff", "#ffd166", o), ["#03071e", "#0a2540"], 5, (180, 260))),
    ("Macaw Rainbow Wings", scene(lambda cx, cy, s, r, o: parrot_shape(cx, cy, s, "#e63946", "#ffd166", o, r), ["#fff8e0", "#ffe9c2"], 6, (170, 250), True)),
    ("Flamingo Yoga Pose", scene(lambda cx, cy, s, r, o: flamingo_shape(cx, cy, s, "#ff8fa3", o), ["#f0ead2", "#e4d9b8"], 5, (180, 260))),
    ("Peacock Garden Party", scene(lambda cx, cy, s, r, o: peacock_shape(cx, cy, s, "#06d6a0", ["#4cc9f0", "#ffd166", "#f15bb5"], o), ["#fdf0ff", "#ffe6f7"], 3, (260, 360))),
    ("Forest Owl Hideaway", scene(lambda cx, cy, s, r, o: owl_shape(cx, cy, s, "#52b788", "#d8f3dc", "#ffd166", o), ["#1b4332", "#2d6a4f"], 5, (180, 260))),
])


# ---- Robots & Gadgets -----------------------------------------------------------

def robot_shape(cx, cy, size, body_color, accent_color, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 45 * s, cy - 60 * s, 90 * s, 70 * s, body_color, rx=14 * s, opacity=opacity),
        rect(cx - 55 * s, cy + 10 * s, 110 * s, 70 * s, body_color, rx=16 * s, opacity=opacity),
        line(cx, cy - 60 * s, cx, cy - 85 * s, accent_color, 6 * s, opacity),
        circle(cx, cy - 90 * s, 8 * s, accent_color, opacity),
        circle(cx - 20 * s, cy - 28 * s, 10 * s, accent_color, opacity),
        circle(cx + 20 * s, cy - 28 * s, 10 * s, accent_color, opacity),
        rect(cx - 25 * s, cy + 35 * s, 50 * s, 24 * s, accent_color, rx=8 * s, opacity=opacity),
        circle(cx - 70 * s, cy + 30 * s, 12 * s, body_color, opacity),
        circle(cx + 70 * s, cy + 30 * s, 12 * s, body_color, opacity),
    ]
    return group(items)


def gear_shape(cx, cy, r, fill, opacity=1, rotation=0):
    items = [circle(cx, cy, r * 0.6, fill, opacity)]
    for i in range(8):
        a = math.radians(i * 45)
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        items.append(f'<rect x="{x-r*0.16:.1f}" y="{y-r*0.16:.1f}" width="{r*0.32:.1f}" height="{r*0.32:.1f}" '
                     f'fill="{fill}" opacity="{opacity:.2f}" transform="rotate({math.degrees(a):.0f} {x:.1f} {y:.1f})"/>')
    items.append(circle(cx, cy, r * 0.24, "#ffffff", opacity * 0.8))
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("robots-gadgets", "Robots & Gadgets", [
    ("Friendly Blue Robot", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#4cc9f0", "#ffd166", o), ["#eaf6ff", "#cdeffd"], 5, (200, 300))),
    ("Gear & Cog Machine", scene(lambda cx, cy, s, r, o: gear_shape(cx, cy, s * 0.5, "#adb5bd", o, r), ["#f8f9fa", "#dee2e6"], 8, (110, 190), True)),
    ("Pink Robo Pal", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#ff8fa3", "#ffffff", o), ["#fff0f5", "#ffe6ee"], 5, (200, 300))),
    ("Neon Circuit Bot", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#3a0ca3", "#00f5d4", o), ["#0d0221", "#190535"], 5, (200, 300))),
    ("Golden Gears at Work", scene(lambda cx, cy, s, r, o: gear_shape(cx, cy, s * 0.5, "#ffd166", o, r), ["#fff8e0", "#ffe9c2"], 8, (110, 190), True)),
    ("Green Guardian Robot", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#52b788", "#fff3b0", o), ["#d8f3dc", "#b7e4c7"], 5, (200, 300))),
    ("Purple Space Robot", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#9b5de5", "#f4a261", o), ["#3a0ca3", "#7209b7"], 5, (200, 300))),
    ("Silver Gear Grid", scene(lambda cx, cy, s, r, o: gear_shape(cx, cy, s * 0.5, "#6c757d", o, r), ["#e9ecef", "#ced4da"], 8, (110, 190), True)),
    ("Orange Helper Bot", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#f4a261", "#264653", o), ["#fff3e0", "#ffe4c2"], 5, (200, 300))),
    ("Rainbow Robot Party", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, rng_choice_colors(r), "#ffffff", o), ["#ff9fbf", "#9fd8ff"], 4, (200, 300))),
    ("Tiny Gadget Bots", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#4361ee", "#ffe66d", o), ["#caf0f8", "#90e0ef"], 6, (140, 220))),
    ("Copper Cog Adventure", scene(lambda cx, cy, s, r, o: gear_shape(cx, cy, s * 0.5, "#b5651d", o, r), ["#fff0e0", "#ffdbb0"], 8, (110, 190), True)),
    ("Midnight Robot Watch", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#212529", "#4cc9f0", o), ["#03071e", "#0a2540"], 5, (200, 300))),
    ("Bubblegum Bot Squad", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#f15bb5", "#c8b6ff", o), ["#fdf0ff", "#ffe6f7"], 5, (200, 300))),
    ("Sunny Yellow Robot", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#ffd166", "#118ab2", o), ["#fff8e0", "#ffefc2"], 5, (200, 300))),
    ("Turquoise Tech Gears", scene(lambda cx, cy, s, r, o: gear_shape(cx, cy, s * 0.5, "#2ec4b6", o, r), ["#e0f7fa", "#b2ebf2"], 8, (110, 190), True)),
    ("Robot Repair Shop", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#adb5bd", "#e63946", o), ["#f1faee", "#dff7e0"], 5, (200, 300))),
    ("Cosmic Cyber Bot", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#7209b7", "#00f5d4", o), ["#020024", "#090979"], 5, (200, 300))),
    ("Cherry Red Robot", scene(lambda cx, cy, s, r, o: robot_shape(cx, cy, s, "#e63946", "#ffe066", o), ["#ffe0ec", "#ffc2d9"], 5, (200, 300))),
    ("Gearbox Wonderland", scene(lambda cx, cy, s, r, o: gear_shape(cx, cy, s * 0.5, "#4a4e69", o, r), ["#e0d4ff", "#c8b6ff"], 8, (110, 190), True)),
])

def rng_choice_colors(seedval):
    palette = ["#ff6fa5", "#4cc9f0", "#ffd166", "#06d6a0", "#9b5de5"]
    return palette[int(abs(seedval)) % len(palette)]


# ---- Pirates & Treasure -----------------------------------------------------------

def ship_shape(cx, cy, size, hull_color, sail_color, opacity=1):
    s = size / 100.0
    items = [
        polygon([(cx-80*s, cy+20*s), (cx+80*s, cy+20*s), (cx+55*s, cy+55*s), (cx-55*s, cy+55*s)], hull_color, opacity),
        rect(cx - 4 * s, cy - 90 * s, 8 * s, 110 * s, "#6b4423", opacity=opacity),
        polygon([(cx+4*s, cy-88*s), (cx+65*s, cy-60*s), (cx+4*s, cy-25*s)], sail_color, opacity),
        polygon([(cx-4*s, cy-70*s), (cx-55*s, cy-45*s), (cx-4*s, cy-20*s)], sail_color, opacity),
    ]
    return group(items)


def chest_shape(cx, cy, size, wood_color, gold_color, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 55 * s, cy - 10 * s, 110 * s, 55 * s, wood_color, rx=6 * s, opacity=opacity),
        f'<path d="M {cx-55*s:.1f} {cy-10*s:.1f} A {55*s:.1f} {35*s:.1f} 0 0 1 {cx+55*s:.1f} {cy-10*s:.1f} Z" '
        f'fill="{wood_color}" opacity="{opacity:.2f}"/>',
        rect(cx - 55 * s, cy - 15 * s, 110 * s, 8 * s, gold_color, opacity=opacity),
        rect(cx - 10 * s, cy - 15 * s, 20 * s, 30 * s, gold_color, rx=4 * s, opacity=opacity),
        circle(cx, cy - 2 * s, 6 * s, "#5b3a1f", opacity),
    ]
    return group(items)


def skull_shape(cx, cy, size, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        circle(cx, cy, 45 * s, "#f4f1ea", opacity),
        rect(cx - 22 * s, cy + 30 * s, 44 * s, 22 * s, "#f4f1ea", rx=6 * s, opacity=opacity),
        ellipse(cx - 18 * s, cy - 5 * s, 12 * s, 15 * s, "#1a1a1a", opacity),
        ellipse(cx + 18 * s, cy - 5 * s, 12 * s, 15 * s, "#1a1a1a", opacity),
        polygon([(cx-6*s, cy+15*s), (cx+6*s, cy+15*s), (cx, cy+28*s)], "#1a1a1a", opacity),
        line(cx - 70 * s, cy + 10 * s, cx + 70 * s, cy - 30 * s, "#f4f1ea", 10 * s, opacity),
        line(cx - 70 * s, cy - 30 * s, cx + 70 * s, cy + 10 * s, "#f4f1ea", 10 * s, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def anchor_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        circle(cx, cy - 55 * s, 14 * s, fill, opacity),
        f'<circle cx="{cx:.1f}" cy="{cy-55*s:.1f}" r="{8*s:.1f}" fill="none" stroke="none"/>',
        line(cx, cy - 45 * s, cx, cy + 55 * s, fill, 10 * s, opacity),
        line(cx - 40 * s, cy - 20 * s, cx + 40 * s, cy - 20 * s, fill, 8 * s, opacity),
        f'<path d="M {cx-45*s:.1f} {cy+30*s:.1f} Q {cx:.1f} {cy+80*s:.1f} {cx+45*s:.1f} {cy+30*s:.1f}" '
        f'fill="none" stroke="{fill}" stroke-width="{10*s:.1f}" stroke-linecap="round" opacity="{opacity:.2f}"/>',
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("pirates-treasure", "Pirates & Treasure", [
    ("Pirate Ship Voyage", scene(lambda cx, cy, s, r, o: ship_shape(cx, cy, s, "#6b4423", "#f4f1ea", o), ["#00b4d8", "#90e0ef"], 4, (240, 340))),
    ("Buried Treasure Chest", scene(lambda cx, cy, s, r, o: chest_shape(cx, cy, s, "#8a5a2b", "#ffd166", o), ["#ffe8b0", "#ffcf8a"], 5, (200, 300))),
    ("Skull & Crossbones Flag", scene(lambda cx, cy, s, r, o: skull_shape(cx, cy, s, o, r), ["#212529", "#495057"], 6, (140, 220), True)),
    ("Anchors Away", scene(lambda cx, cy, s, r, o: anchor_shape(cx, cy, s, "#023e8a", o, r), ["#caf0f8", "#90e0ef"], 6, (150, 230), True)),
    ("High Seas Adventure", scene(lambda cx, cy, s, r, o: ship_shape(cx, cy, s, "#e76f51", "#fff3e0", o), ["#0077b6", "#00b4d8"], 4, (240, 340))),
    ("Golden Doubloon Chest", scene(lambda cx, cy, s, r, o: chest_shape(cx, cy, s, "#6b4423", "#f4a261", o), ["#fff8e0", "#ffe9c2"], 5, (200, 300))),
    ("Jolly Roger Sunset", scene(lambda cx, cy, s, r, o: skull_shape(cx, cy, s, o, r), ["#ff9f7b", "#ff6f91"], 6, (140, 220), True)),
    ("Sailor's Anchor Bay", scene(lambda cx, cy, s, r, o: anchor_shape(cx, cy, s, "#118ab2", o, r), ["#eaf6ff", "#cdeffd"], 6, (150, 230), True)),
    ("Storm-Tossed Ship", scene(lambda cx, cy, s, r, o: ship_shape(cx, cy, s, "#495057", "#e9ecef", o), ["#2b2d42", "#495057"], 4, (240, 340))),
    ("Emerald Isle Treasure", scene(lambda cx, cy, s, r, o: chest_shape(cx, cy, s, "#2d6a4f", "#ffd166", o), ["#d8f3dc", "#b7e4c7"], 5, (200, 300))),
    ("Ghost Ship Skulls", scene(lambda cx, cy, s, r, o: skull_shape(cx, cy, s, o, r), ["#0d1b4c", "#1a1a40"], 6, (140, 220), True)),
    ("Purple Pirate Anchor", scene(lambda cx, cy, s, r, o: anchor_shape(cx, cy, s, "#7209b7", o, r), ["#f3e8ff", "#e0d4ff"], 6, (150, 230), True)),
    ("Tropical Pirate Cove", scene(lambda cx, cy, s, r, o: ship_shape(cx, cy, s, "#f4a261", "#fff3e0", o), ["#06d6a0", "#4cc9f0"], 4, (240, 340))),
    ("Ruby Jeweled Chest", scene(lambda cx, cy, s, r, o: chest_shape(cx, cy, s, "#5b3a1f", "#e63946", o), ["#ffe0ec", "#ffc2d9"], 5, (200, 300))),
    ("Pink Pirate Party", scene(lambda cx, cy, s, r, o: skull_shape(cx, cy, s, o, r), ["#ff9fd6", "#c8b6ff"], 6, (140, 220), True)),
    ("Deep Sea Anchor Drop", scene(lambda cx, cy, s, r, o: anchor_shape(cx, cy, s, "#00b4d8", o, r), ["#03045e", "#0077b6"], 6, (150, 230), True)),
    ("Moonlit Pirate Sails", scene(lambda cx, cy, s, r, o: ship_shape(cx, cy, s, "#212529", "#adb5bd", o), ["#03071e", "#0a2540"], 4, (240, 340))),
    ("Silver Treasure Hoard", scene(lambda cx, cy, s, r, o: chest_shape(cx, cy, s, "#6c757d", "#e9ecef", o), ["#e0f7fa", "#b2ebf2"], 5, (200, 300))),
    ("Rainbow Pirate Flag", scene(lambda cx, cy, s, r, o: skull_shape(cx, cy, s, o, r), ["#ff9fbf", "#ffd39f"], 6, (140, 220), True)),
    ("Captain's Golden Anchor", scene(lambda cx, cy, s, r, o: anchor_shape(cx, cy, s, "#ffd166", o, r), ["#fff3e0", "#ffe4c2"], 6, (150, 230), True)),
])


# ---- Camping & Outdoors -----------------------------------------------------------

def tent_shape(cx, cy, size, fabric_color, opacity=1):
    s = size / 100.0
    items = [
        polygon([(cx-70*s, cy+40*s), (cx, cy-70*s), (cx+70*s, cy+40*s)], fabric_color, opacity),
        polygon([(cx-20*s, cy+40*s), (cx, cy-10*s), (cx+20*s, cy+40*s)], "#5b3a1f", opacity),
        line(cx, cy - 70 * s, cx, cy - 90 * s, "#5b3a1f", 5 * s, opacity),
    ]
    return group(items)


def campfire_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        polygon([(cx-40*s, cy+30*s), (cx+10*s, cy+15*s), (cx+40*s, cy+30*s)], "#8a5a2b", opacity),
        polygon([(cx-40*s, cy+15*s), (cx+10*s, cy+30*s), (cx+40*s, cy+15*s)], "#6b4423", opacity),
        path(f"M {cx-18*s} {cy+15*s} C {cx-25*s} {cy-15*s}, {cx-5*s} {cy-20*s}, {cx} {cy-45*s} "
             f"C {cx+5*s} {cy-20*s}, {cx+25*s} {cy-15*s}, {cx+18*s} {cy+15*s} "
             f"C {cx+10*s} {cy+5*s}, {cx-10*s} {cy+5*s}, {cx-18*s} {cy+15*s} Z", "#f4a261", opacity),
        path(f"M {cx-8*s} {cy+10*s} C {cx-10*s} {cy-8*s}, {cx-2*s} {cy-10*s}, {cx} {cy-25*s} "
             f"C {cx+2*s} {cy-10*s}, {cx+10*s} {cy-8*s}, {cx+8*s} {cy+10*s} Z", "#ffd166", opacity),
    ]
    return group(items)


def lantern_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 6 * s, cy - 60 * s, 12 * s, 15 * s, "#495057", opacity=opacity),
        rect(cx - 35 * s, cy - 45 * s, 70 * s, 80 * s, "#495057", rx=8 * s, opacity=opacity),
        rect(cx - 26 * s, cy - 36 * s, 52 * s, 62 * s, "#fff3b0", rx=4 * s, opacity=opacity),
        circle(cx, cy - 5 * s, 16 * s, "#ffd166", opacity),
    ]
    return group(items)


cat("camping-outdoors", "Camping & Outdoors", [
    ("Starlit Tent Camp", scene(lambda cx, cy, s, r, o: tent_shape(cx, cy, s, "#e76f51", o), ["#0d1b4c", "#1a1a40"], 5, (200, 300))),
    ("Cozy Campfire Glow", scene(lambda cx, cy, s, r, o: campfire_shape(cx, cy, s, o), ["#2b2d42", "#495057"], 6, (150, 230))),
    ("Camping Lantern Light", scene(lambda cx, cy, s, r, o: lantern_shape(cx, cy, s, o), ["#0f2027", "#2c5364"], 5, (180, 260))),
    ("Green Forest Tents", scene(lambda cx, cy, s, r, o: tent_shape(cx, cy, s, "#52b788", o), ["#d8f3dc", "#b7e4c7"], 5, (200, 300))),
    ("Marshmallow Roast Fire", scene(lambda cx, cy, s, r, o: campfire_shape(cx, cy, s, o), ["#ffe8b0", "#ffcf8a"], 6, (150, 230))),
    ("Blue Mountain Camp", scene(lambda cx, cy, s, r, o: tent_shape(cx, cy, s, "#4cc9f0", o), ["#eaf6ff", "#cdeffd"], 5, (200, 300))),
    ("Firefly Lantern Night", scene(lambda cx, cy, s, r, o: lantern_shape(cx, cy, s, o), ["#03071e", "#0a2540"], 5, (180, 260))),
    ("Sunset Campsite", scene(lambda cx, cy, s, r, o: tent_shape(cx, cy, s, "#ffd166", o), ["#ff9f7b", "#ff6f91"], 5, (200, 300))),
    ("Woodland Campfire Circle", scene(lambda cx, cy, s, r, o: campfire_shape(cx, cy, s, o), ["#1b4332", "#2d6a4f"], 6, (150, 230))),
    ("Purple Twilight Tent", scene(lambda cx, cy, s, r, o: tent_shape(cx, cy, s, "#9b5de5", o), ["#3a0ca3", "#7209b7"], 5, (200, 300))),
    ("Glowing Trail Lanterns", scene(lambda cx, cy, s, r, o: lantern_shape(cx, cy, s, o), ["#eaf7ff", "#dff3ff"], 5, (180, 260))),
    ("Pink Adventure Tent", scene(lambda cx, cy, s, r, o: tent_shape(cx, cy, s, "#ff8fa3", o), ["#fff0f5", "#ffe6ee"], 5, (200, 300))),
    ("Late Night Fire Stories", scene(lambda cx, cy, s, r, o: campfire_shape(cx, cy, s, o), ["#000814", "#001d3d"], 6, (150, 230))),
    ("Rustic Lantern Glow", scene(lambda cx, cy, s, r, o: lantern_shape(cx, cy, s, o), ["#fff3e0", "#ffe4c2"], 5, (180, 260))),
    ("Alpine Camp Retreat", scene(lambda cx, cy, s, r, o: tent_shape(cx, cy, s, "#118ab2", o), ["#caf0f8", "#90e0ef"], 5, (200, 300))),
    ("Golden Ember Campfire", scene(lambda cx, cy, s, r, o: campfire_shape(cx, cy, s, o), ["#6b4423", "#5b3a1f"], 6, (150, 230))),
    ("Misty Morning Lantern", scene(lambda cx, cy, s, r, o: lantern_shape(cx, cy, s, o), ["#a8dadc", "#457b9d"], 5, (180, 260))),
    ("Desert Star Camp", scene(lambda cx, cy, s, r, o: tent_shape(cx, cy, s, "#f4a261", o), ["#020024", "#090979"], 5, (200, 300))),
    ("Summer Campfire Fun", scene(lambda cx, cy, s, r, o: campfire_shape(cx, cy, s, o), ["#eafff1", "#d0f4de"], 6, (150, 230))),
    ("Trailhead Lantern Path", scene(lambda cx, cy, s, r, o: lantern_shape(cx, cy, s, o), ["#f0ead2", "#e4d9b8"], 5, (180, 260))),
])


# ---- Circus & Carnival -----------------------------------------------------------

def big_top_shape(cx, cy, size, stripe1, stripe2, opacity=1):
    s = size / 100.0
    items = [polygon([(cx-90*s, cy+40*s), (cx, cy-100*s), (cx+90*s, cy+40*s)], stripe1, opacity)]
    for i in range(-3, 4):
        items.append(polygon([(cx+i*24*s, cy-100*s+abs(i)*8*s), (cx+i*24*s+12*s, cy-100*s+abs(i)*8*s),
                               (cx+i*24*s+6*s, cy+40*s)], stripe2, opacity * 0.8))
    items.append(circle(cx, cy - 100 * s, 10 * s, stripe2, opacity))
    for dx in (-45, 0, 45):
        items.append(polygon([(cx+dx*s-14*s, cy+40*s), (cx+dx*s+14*s, cy+40*s), (cx+dx*s, cy+65*s)], stripe1, opacity))
    return group(items)


def ferris_wheel_shape(cx, cy, r, fill, gondola_color, opacity=1, rotation=0):
    items = [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{fill}" '
             f'stroke-width="{r*0.1:.1f}" opacity="{opacity:.2f}"/>']
    for i in range(8):
        a = math.radians(i * 45 + rotation)
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        items.append(line(cx, cy, x, y, fill, r * 0.04, opacity))
        items.append(circle(x, y, r * 0.14, gondola_color, opacity))
    items.append(circle(cx, cy, r * 0.1, fill, opacity))
    return group(items)


def popcorn_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    # Deterministic (not module-level random) so re-running the generator
    # reproduces identical output, seeded from this instance's own position.
    local_rng = random.Random(f"popcorn-{cx:.2f}-{cy:.2f}-{size:.2f}")
    items = [polygon([(cx-30*s, cy), (cx+30*s, cy), (cx+22*s, cy+60*s), (cx-22*s, cy+60*s)], "#e63946", opacity)]
    for i in range(4):
        items.append(line(cx - 24 * s + i * 16 * s, cy, cx - 20 * s + i * 16 * s, cy + 58 * s, "#ffffff", 6 * s, opacity))
    for _ in range(10):
        jx = local_rng.uniform(-40, 40) * s
        jy = local_rng.uniform(-40, 40) * s * 2
        items.append(circle(cx + jx, cy - 20 * s + jy, 12 * s, "#fff3b0", opacity))
    return group(items)


cat("circus-carnival", "Circus & Carnival", [
    ("Big Top Circus Tent", scene(lambda cx, cy, s, r, o: big_top_shape(cx, cy, s, "#e63946", "#f4f1ea", o), ["#ffe066", "#ffd166"], 4, (240, 340))),
    ("Colorful Balloon Bunch", scene(lambda cx, cy, s, r, o: balloon_shape(cx, cy, s, rng_choice_colors(r), o), ["#a8e6ff", "#d6f0ff"], 8, (140, 220))),
    ("Spinning Ferris Wheel", scene(lambda cx, cy, s, r, o: ferris_wheel_shape(cx, cy, s * 0.5, "#4361ee", "#ffd166", o, r), ["#eaf6ff", "#cdeffd"], 3, (300, 420), True)),
    ("Buttery Popcorn Fun", scene(lambda cx, cy, s, r, o: popcorn_shape(cx, cy, s, o), ["#fff3e0", "#ffe4c2"], 7, (150, 230))),
    ("Purple Carnival Tent", scene(lambda cx, cy, s, r, o: big_top_shape(cx, cy, s, "#7209b7", "#f4f1ea", o), ["#fdf0ff", "#ffe6f7"], 4, (240, 340))),
    ("Rainbow Balloon Sky", scene(lambda cx, cy, s, r, o: balloon_shape(cx, cy, s, rng_choice_colors(r), o), ["#ff9fbf", "#9fd8ff"], 8, (140, 220))),
    ("Night Carnival Lights", scene(lambda cx, cy, s, r, o: ferris_wheel_shape(cx, cy, s * 0.5, "#f15bb5", "#4cc9f0", o, r), ["#0d1b4c", "#1a1a40"], 3, (300, 420), True)),
    ("Circus Popcorn Stand", scene(lambda cx, cy, s, r, o: popcorn_shape(cx, cy, s, o), ["#eafff1", "#d0f4de"], 7, (150, 230))),
    ("Blue Striped Big Top", scene(lambda cx, cy, s, r, o: big_top_shape(cx, cy, s, "#118ab2", "#f4f1ea", o), ["#caf0f8", "#90e0ef"], 4, (240, 340))),
    ("Golden Ferris Wheel", scene(lambda cx, cy, s, r, o: ferris_wheel_shape(cx, cy, s * 0.5, "#ffd166", "#e63946", o, r), ["#fff8e0", "#ffe9c2"], 3, (300, 420), True)),
    ("Party Balloon Cluster", scene(lambda cx, cy, s, r, o: balloon_shape(cx, cy, s, rng_choice_colors(r), o), ["#fff0f5", "#ffe6ee"], 8, (140, 220))),
    ("Sunset Carnival Fair", scene(lambda cx, cy, s, r, o: ferris_wheel_shape(cx, cy, s * 0.5, "#ff6f91", "#ffd166", o, r), ["#ff9f7b", "#ff6f91"], 3, (300, 420), True)),
    ("Green Big Top Show", scene(lambda cx, cy, s, r, o: big_top_shape(cx, cy, s, "#2d6a4f", "#f4f1ea", o), ["#d8f3dc", "#b7e4c7"], 4, (240, 340))),
    ("Caramel Popcorn Party", scene(lambda cx, cy, s, r, o: popcorn_shape(cx, cy, s, o), ["#f0ead2", "#e4d9b8"], 7, (150, 230))),
    ("Teal Carnival Delight", scene(lambda cx, cy, s, r, o: big_top_shape(cx, cy, s, "#2ec4b6", "#f4f1ea", o), ["#e0f7fa", "#b2ebf2"], 4, (240, 340))),
    ("Pastel Balloon Drift", scene(lambda cx, cy, s, r, o: balloon_shape(cx, cy, s, rng_choice_colors(r), o), ["#f3e8ff", "#e0f7ff"], 8, (140, 220))),
    ("Twilight Ferris Wheel", scene(lambda cx, cy, s, r, o: ferris_wheel_shape(cx, cy, s * 0.5, "#9b5de5", "#00f5d4", o, r), ["#03071e", "#0a2540"], 3, (300, 420), True)),
    ("Salty Sweet Popcorn", scene(lambda cx, cy, s, r, o: popcorn_shape(cx, cy, s, o), ["#ffe0ec", "#ffc2d9"], 7, (150, 230))),
    ("Red & White Big Top", scene(lambda cx, cy, s, r, o: big_top_shape(cx, cy, s, "#ef476f", "#f4f1ea", o), ["#fff3b0", "#ffe066"], 4, (240, 340))),
    ("Carnival Balloon Release", scene(lambda cx, cy, s, r, o: balloon_shape(cx, cy, s, rng_choice_colors(r), o), ["#eaf7ff", "#dff3ff"], 8, (140, 220))),
])


# ---- Construction & Diggers -----------------------------------------------------------

def dump_truck_shape(cx, cy, size, body_color, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 90 * s, cy - 10 * s, 70 * s, 55 * s, body_color, rx=6 * s, opacity=opacity),
        rect(cx - 20 * s, cy - 40 * s, 90 * s, 85 * s, body_color, rx=8 * s, opacity=opacity),
        rect(cx - 82 * s, cy - 2 * s, 40 * s, 30 * s, "#a6e3ff", rx=4 * s, opacity=opacity),
        circle(cx - 55 * s, cy + 55 * s, 20 * s, "#1a1a1a", opacity),
        circle(cx + 40 * s, cy + 55 * s, 20 * s, "#1a1a1a", opacity),
    ]
    return group(items)


def crane_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 8 * s, cy - 20 * s, 16 * s, 130 * s, fill, opacity=opacity),
        line(cx, cy - 20 * s, cx + 90 * s, cy - 20 * s, fill, 8 * s, opacity),
        line(cx, cy - 20 * s, cx - 30 * s, cy - 20 * s, fill, 8 * s, opacity),
        line(cx + 80 * s, cy - 20 * s, cx + 80 * s, cy + 30 * s, "#495057", 3 * s, opacity),
        rect(cx + 72 * s, cy + 30 * s, 16 * s, 14 * s, "#495057", opacity=opacity),
        rect(cx - 30 * s, cy + 108 * s, 60 * s, 22 * s, fill, rx=4 * s, opacity=opacity),
    ]
    return group(items)


def cone_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        polygon([(cx-35*s, cy+50*s), (cx+35*s, cy+50*s), (cx+12*s, cy-50*s), (cx-12*s, cy-50*s)], "#f4a261", opacity),
        rect(cx - 40 * s, cy + 42 * s, 80 * s, 16 * s, "#e76f51", rx=4 * s, opacity=opacity),
        polygon([(cx-18*s, cy+5*s), (cx+18*s, cy+5*s), (cx+8*s, cy-25*s), (cx-8*s, cy-25*s)], "#ffffff", opacity * 0.8),
    ]
    return group(items)


def hardhat_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        f'<path d="M {cx-55*s:.1f} {cy+10*s:.1f} A {55*s:.1f} {50*s:.1f} 0 0 1 {cx+55*s:.1f} {cy+10*s:.1f} Z" '
        f'fill="{fill}" opacity="{opacity:.2f}"/>',
        rect(cx - 62 * s, cy + 5 * s, 124 * s, 16 * s, fill, rx=8 * s, opacity=opacity),
        rect(cx - 6 * s, cy - 45 * s, 12 * s, 20 * s, fill, rx=4 * s, opacity=opacity * 0.8),
    ]
    return group(items)


cat("construction-diggers", "Construction & Diggers", [
    ("Big Dump Truck", scene(lambda cx, cy, s, r, o: dump_truck_shape(cx, cy, s, "#ffd166", o), ["#a8dadc", "#457b9d"], 5, (180, 260))),
    ("Tower Crane at Work", scene(lambda cx, cy, s, r, o: crane_shape(cx, cy, s, "#e76f51", o), ["#eaf6ff", "#cdeffd"], 3, (280, 380))),
    ("Traffic Cone Row", scene(lambda cx, cy, s, r, o: cone_shape(cx, cy, s, o), ["#fff3e0", "#ffe4c2"], 8, (140, 220))),
    ("Hard Hat Zone", scene(lambda cx, cy, s, r, o: hardhat_shape(cx, cy, s, "#ffd166", o), ["#fff8e0", "#ffe9c2"], 7, (140, 220))),
    ("Yellow Dump Trucks", scene(lambda cx, cy, s, r, o: dump_truck_shape(cx, cy, s, "#f4a261", o), ["#fff3e0", "#ffe4c2"], 5, (180, 260))),
    ("Red Crane Skyline", scene(lambda cx, cy, s, r, o: crane_shape(cx, cy, s, "#e63946", o), ["#caf0f8", "#90e0ef"], 3, (280, 380))),
    ("Orange Cone Path", scene(lambda cx, cy, s, r, o: cone_shape(cx, cy, s, o), ["#eafff1", "#d0f4de"], 8, (140, 220))),
    ("Blue Hard Hat Crew", scene(lambda cx, cy, s, r, o: hardhat_shape(cx, cy, s, "#4361ee", o), ["#dbe9ff", "#a8c6ff"], 7, (140, 220))),
    ("Green Machine Truck", scene(lambda cx, cy, s, r, o: dump_truck_shape(cx, cy, s, "#52b788", o), ["#d8f3dc", "#b7e4c7"], 5, (180, 260))),
    ("Golden Hour Crane", scene(lambda cx, cy, s, r, o: crane_shape(cx, cy, s, "#ffd166", o), ["#ffe8b0", "#ffcf8a"], 3, (280, 380))),
    ("Cone Construction Zone", scene(lambda cx, cy, s, r, o: cone_shape(cx, cy, s, o), ["#fff0f5", "#ffe6ee"], 8, (140, 220))),
    ("Pink Hard Hat Fun", scene(lambda cx, cy, s, r, o: hardhat_shape(cx, cy, s, "#ff8fa3", o), ["#ffe0ec", "#ffc2d9"], 7, (140, 220))),
    ("Purple Dump Truck Fleet", scene(lambda cx, cy, s, r, o: dump_truck_shape(cx, cy, s, "#9b5de5", o), ["#f3e8ff", "#e0d4ff"], 5, (180, 260))),
    ("Night Shift Crane", scene(lambda cx, cy, s, r, o: crane_shape(cx, cy, s, "#adb5bd", o), ["#03071e", "#0a2540"], 3, (280, 380))),
    ("Rainbow Traffic Cones", scene(lambda cx, cy, s, r, o: cone_shape(cx, cy, s, o), ["#ff9fbf", "#9fd8ff"], 8, (140, 220))),
    ("Teal Hard Hat Team", scene(lambda cx, cy, s, r, o: hardhat_shape(cx, cy, s, "#2ec4b6", o), ["#e0f7fa", "#b2ebf2"], 7, (140, 220))),
    ("Sunny Site Truck", scene(lambda cx, cy, s, r, o: dump_truck_shape(cx, cy, s, "#ffe066", o), ["#fff8e0", "#ffefc2"], 5, (180, 260))),
    ("Sky High Crane Lift", scene(lambda cx, cy, s, r, o: crane_shape(cx, cy, s, "#118ab2", o), ["#a8e6ff", "#dff7ff"], 3, (280, 380))),
    ("Cone Zone Party", scene(lambda cx, cy, s, r, o: cone_shape(cx, cy, s, o), ["#f0ead2", "#e4d9b8"], 8, (140, 220))),
    ("Builder's Hard Hat Day", scene(lambda cx, cy, s, r, o: hardhat_shape(cx, cy, s, "#e76f51", o), ["#fff3e0", "#ffe4c2"], 7, (140, 220))),
])


# ---- School & Learning -----------------------------------------------------------

def book_shape(cx, cy, size, cover_color, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        rect(cx - 50 * s, cy - 40 * s, 100 * s, 80 * s, cover_color, rx=6 * s, opacity=opacity),
        rect(cx - 42 * s, cy - 34 * s, 84 * s, 68 * s, "#fdfdfd", rx=4 * s, opacity=opacity),
        line(cx, cy - 34 * s, cx, cy + 34 * s, cover_color, 3 * s, opacity * 0.6),
        line(cx - 30 * s, cy - 15 * s, cx - 8 * s, cy - 15 * s, "#adb5bd", 3 * s, opacity),
        line(cx - 30 * s, cy, cx - 8 * s, cy, "#adb5bd", 3 * s, opacity),
        line(cx + 8 * s, cy - 15 * s, cx + 30 * s, cy - 15 * s, "#adb5bd", 3 * s, opacity),
        line(cx + 8 * s, cy, cx + 30 * s, cy, "#adb5bd", 3 * s, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def pencil_shape(cx, cy, size, body_color, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        rect(cx - 15 * s, cy - 90 * s, 30 * s, 140 * s, body_color, opacity=opacity),
        polygon([(cx-15*s, cy+50*s), (cx+15*s, cy+50*s), (cx, cy+85*s)], "#f4a261", opacity),
        rect(cx - 15 * s, cy - 105 * s, 30 * s, 18 * s, "#adb5bd", rx=4 * s, opacity=opacity),
        rect(cx - 15 * s, cy - 90 * s, 30 * s, 8 * s, "#ffe066", opacity=opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def apple_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        circle(cx - 20 * s, cy + 5 * s, 32 * s, fill, opacity),
        circle(cx + 20 * s, cy + 5 * s, 32 * s, fill, opacity),
        circle(cx, cy + 15 * s, 34 * s, fill, opacity),
        line(cx, cy - 30 * s, cx, cy - 50 * s, "#6b4423", 5 * s, opacity),
        ellipse(cx + 14 * s, cy - 42 * s, 14 * s, 8 * s, "#52b788", opacity, transform=f"rotate(-20 {cx+14*s} {cy-42*s})"),
    ]
    return group(items)


def backpack_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 45 * s, cy - 30 * s, 90 * s, 100 * s, fill, rx=20 * s, opacity=opacity),
        rect(cx - 30 * s, cy - 50 * s, 60 * s, 30 * s, fill, rx=14 * s, opacity=opacity),
        rect(cx - 25 * s, cy + 10 * s, 50 * s, 40 * s, "#ffffff", rx=10 * s, opacity=opacity * 0.85),
        circle(cx, cy + 30 * s, 6 * s, "#495057", opacity),
    ]
    return group(items)


cat("school-learning", "School & Learning", [
    ("Storybook Stack", scene(lambda cx, cy, s, r, o: book_shape(cx, cy, s, "#ef476f", o, r), ["#fff0f5", "#ffe6ee"], 6, (170, 250), True)),
    ("Pencil Case Colors", scene(lambda cx, cy, s, r, o: pencil_shape(cx, cy, s, rng_choice_colors(r), o, r * 0.1), ["#fff8e0", "#ffefc2"], 8, (130, 210), True)),
    ("Apple for the Teacher", scene(lambda cx, cy, s, r, o: apple_shape(cx, cy, s, "#e63946", o), ["#eafff1", "#d0f4de"], 6, (160, 240))),
    ("Ready for School Backpack", scene(lambda cx, cy, s, r, o: backpack_shape(cx, cy, s, "#4361ee", o), ["#eaf6ff", "#cdeffd"], 5, (180, 260))),
    ("Blue Book Collection", scene(lambda cx, cy, s, r, o: book_shape(cx, cy, s, "#118ab2", o, r), ["#caf0f8", "#90e0ef"], 6, (170, 250), True)),
    ("Rainbow Pencil Party", scene(lambda cx, cy, s, r, o: pencil_shape(cx, cy, s, rng_choice_colors(r), o, r * 0.1), ["#ff9fbf", "#9fd8ff"], 8, (130, 210), True)),
    ("Green Apple Orchard", scene(lambda cx, cy, s, r, o: apple_shape(cx, cy, s, "#52b788", o), ["#d8f3dc", "#b7e4c7"], 6, (160, 240))),
    ("Pink Backpack Ready", scene(lambda cx, cy, s, r, o: backpack_shape(cx, cy, s, "#ff8fa3", o), ["#fff0f5", "#ffe6ee"], 5, (180, 260))),
    ("Purple Reading Corner", scene(lambda cx, cy, s, r, o: book_shape(cx, cy, s, "#9b5de5", o, r), ["#f3e8ff", "#e0d4ff"], 6, (170, 250), True)),
    ("Classic Yellow Pencils", scene(lambda cx, cy, s, r, o: pencil_shape(cx, cy, s, "#ffd166", o, r * 0.1), ["#fff3b0", "#ffe066"], 8, (130, 210), True)),
    ("Golden Apple Day", scene(lambda cx, cy, s, r, o: apple_shape(cx, cy, s, "#ffd166", o), ["#fff8e0", "#ffe9c2"], 6, (160, 240))),
    ("Orange Backpack Adventure", scene(lambda cx, cy, s, r, o: backpack_shape(cx, cy, s, "#f4a261", o), ["#fff3e0", "#ffe4c2"], 5, (180, 260))),
    ("Teal Textbook Tower", scene(lambda cx, cy, s, r, o: book_shape(cx, cy, s, "#2ec4b6", o, r), ["#e0f7fa", "#b2ebf2"], 6, (170, 250), True)),
    ("Back to School Pencils", scene(lambda cx, cy, s, r, o: pencil_shape(cx, cy, s, rng_choice_colors(r), o, r * 0.1), ["#eafff1", "#d0f4de"], 8, (130, 210), True)),
    ("Red Apple Classroom", scene(lambda cx, cy, s, r, o: apple_shape(cx, cy, s, "#ef476f", o), ["#ffe0ec", "#ffc2d9"], 6, (160, 240))),
    ("Sky Blue Backpack Set", scene(lambda cx, cy, s, r, o: backpack_shape(cx, cy, s, "#4cc9f0", o), ["#a8e6ff", "#dff7ff"], 5, (180, 260))),
    ("Sunshine Storybooks", scene(lambda cx, cy, s, r, o: book_shape(cx, cy, s, "#ffd166", o, r), ["#fff8e0", "#ffefc2"], 6, (170, 250), True)),
    ("Lavender Pencil Cup", scene(lambda cx, cy, s, r, o: pencil_shape(cx, cy, s, "#c8b6ff", o, r * 0.1), ["#f3e8ff", "#e0d4ff"], 8, (130, 210), True)),
    ("Autumn Apple Harvest", scene(lambda cx, cy, s, r, o: apple_shape(cx, cy, s, "#e76f51", o), ["#ffe8b0", "#ffcf8a"], 6, (160, 240))),
    ("First Day Backpack", scene(lambda cx, cy, s, r, o: backpack_shape(cx, cy, s, "#06d6a0", o), ["#eafff1", "#d0f4de"], 5, (180, 260))),
])


# ---- Safari & Desert -----------------------------------------------------------

def cactus_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        rect(cx - 18 * s, cy - 60 * s, 36 * s, 130 * s, fill, rx=18 * s, opacity=opacity),
        rect(cx - 55 * s, cy - 20 * s, 32 * s, 70 * s, fill, rx=16 * s, opacity=opacity),
        rect(cx + 23 * s, cy - 40 * s, 32 * s, 70 * s, fill, rx=16 * s, opacity=opacity),
        circle(cx, cy - 65 * s, 5 * s, "#ffb703", opacity),
        circle(cx - 12 * s, cy - 30 * s, 5 * s, "#ffb703", opacity),
    ]
    return group(items)


def camel_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        ellipse(cx, cy + 10 * s, 55 * s, 32 * s, fill, opacity),
        ellipse(cx - 10 * s, cy - 20 * s, 26 * s, 24 * s, fill, opacity),
        f'<path d="M {cx-45*s:.1f} {cy-10*s:.1f} C {cx-30*s:.1f} {cy-70*s:.1f}, {cx+5*s:.1f} {cy-70*s:.1f}, '
        f'{cx+10*s:.1f} {cy-25*s:.1f}" fill="{fill}" opacity="{opacity:.2f}"/>',
        rect(cx + 30 * s, cy - 45 * s, 16 * s, 60 * s, fill, rx=8 * s, opacity=opacity),
        circle(cx + 40 * s, cy - 50 * s, 4 * s, "#1a1a1a", opacity),
        rect(cx - 40 * s, cy + 35 * s, 8 * s, 30 * s, fill, opacity=opacity),
        rect(cx + 30 * s, cy + 35 * s, 8 * s, 30 * s, fill, opacity=opacity),
    ]
    return group(items)


def elephant_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        circle(cx, cy, 55 * s, fill, opacity),
        ellipse(cx - 60 * s, cy - 20 * s, 30 * s, 38 * s, fill, opacity),
        f'<path d="M {cx+30*s:.1f} {cy+30*s:.1f} C {cx+45*s:.1f} {cy+50*s:.1f}, {cx+40*s:.1f} {cy+85*s:.1f}, '
        f'{cx+20*s:.1f} {cy+85*s:.1f}" fill="none" stroke="{fill}" stroke-width="{16*s:.1f}" '
        f'stroke-linecap="round" opacity="{opacity:.2f}"/>',
        circle(cx + 12 * s, cy - 10 * s, 6 * s, "#1a1a1a", opacity),
        ellipse(cx - 10 * s, cy - 60 * s, 14 * s, 10 * s, fill, opacity),
        ellipse(cx + 22 * s, cy - 60 * s, 14 * s, 10 * s, fill, opacity),
    ]
    return group(items)


def giraffe_shape(cx, cy, size, fill, spot_color, opacity=1):
    s = size / 100.0
    # Deterministic (not module-level random) so re-running the generator
    # reproduces identical output, seeded from this instance's own position.
    local_rng = random.Random(f"giraffe-{cx:.2f}-{cy:.2f}-{size:.2f}")
    items = [
        rect(cx - 12 * s, cy - 20 * s, 24 * s, 100 * s, fill, rx=10 * s, opacity=opacity),
        circle(cx, cy - 40 * s, 32 * s, fill, opacity),
        ellipse(cx - 8 * s, cy - 72 * s, 5 * s, 14 * s, fill, opacity),
        ellipse(cx + 8 * s, cy - 72 * s, 5 * s, 14 * s, fill, opacity),
        circle(cx + 10 * s, cy - 44 * s, 4 * s, "#1a1a1a", opacity),
        ellipse(cx, cy + 40 * s, 30 * s, 22 * s, fill, opacity),
    ]
    for _ in range(6):
        jx = local_rng.uniform(-30, 30) * s * 0.6
        jy = local_rng.uniform(-30, 30) * s * 0.6
        items.append(circle(cx + jx, cy + 20 * s + jy, 8 * s, spot_color, opacity))
    return group(items)


def zebra_shape(cx, cy, size, opacity=1):
    s = size / 100.0
    items = [
        circle(cx, cy, 55 * s, "#fdfdfd", opacity),
        ellipse(cx - 48 * s, cy - 42 * s, 12 * s, 20 * s, "#fdfdfd", opacity),
        ellipse(cx + 48 * s, cy - 42 * s, 12 * s, 20 * s, "#fdfdfd", opacity),
        circle(cx - 20 * s, cy - 8 * s, 6 * s, "#1a1a1a", opacity),
        circle(cx + 20 * s, cy - 8 * s, 6 * s, "#1a1a1a", opacity),
    ]
    for i in range(6):
        y = cy - 45 * s + i * 16 * s
        items.append(f'<path d="M {cx-50*s:.1f} {y:.1f} Q {cx:.1f} {y+10*s:.1f} {cx+50*s:.1f} {y:.1f}" '
                     f'fill="none" stroke="#1a1a1a" stroke-width="{6*s:.1f}" opacity="{opacity*0.7:.2f}"/>')
    return group(items)


cat("safari-desert", "Safari & Desert", [
    ("Desert Cactus Bloom", scene(lambda cx, cy, s, r, o: cactus_shape(cx, cy, s, "#2d6a4f", o), ["#ffe8b0", "#ffcf8a"], 6, (180, 260))),
    ("Camel Caravan", scene(lambda cx, cy, s, r, o: camel_shape(cx, cy, s, "#e9c46a", o), ["#f4a261", "#e76f51"], 5, (190, 270))),
    ("Gentle Elephant Herd", scene(lambda cx, cy, s, r, o: elephant_shape(cx, cy, s, "#8d99ae", o), ["#eafff1", "#d0f4de"], 5, (200, 280))),
    ("Tall Giraffe Savanna", scene(lambda cx, cy, s, r, o: giraffe_shape(cx, cy, s, "#f4a261", "#e76f51", o), ["#fff3e0", "#ffe4c2"], 5, (200, 300))),
    ("Striped Zebra Crossing", scene(lambda cx, cy, s, r, o: zebra_shape(cx, cy, s, o), ["#fdf6ec", "#f0ead2"], 6, (180, 260))),
    ("Green Oasis Cactus", scene(lambda cx, cy, s, r, o: cactus_shape(cx, cy, s, "#52b788", o), ["#d8f3dc", "#b7e4c7"], 6, (180, 260))),
    ("Sandy Dune Camels", scene(lambda cx, cy, s, r, o: camel_shape(cx, cy, s, "#c9a066", o), ["#ffe8b0", "#ffcf8a"], 5, (190, 270))),
    ("Baby Elephant Splash", scene(lambda cx, cy, s, r, o: elephant_shape(cx, cy, s, "#adb5bd", o), ["#a8e6ff", "#dff7ff"], 5, (200, 280))),
    ("Sunset Giraffe Silhouette", scene(lambda cx, cy, s, r, o: giraffe_shape(cx, cy, s, "#e76f51", "#6b4423", o), ["#ff9f7b", "#ff6f91"], 5, (200, 300))),
    ("Zebra Herd at Dusk", scene(lambda cx, cy, s, r, o: zebra_shape(cx, cy, s, o), ["#ff9f7b", "#ff6f91"], 6, (180, 260))),
    ("Blue Cactus Garden", scene(lambda cx, cy, s, r, o: cactus_shape(cx, cy, s, "#2a9d8f", o), ["#caf0f8", "#90e0ef"], 6, (180, 260))),
    ("Golden Hour Camel Trek", scene(lambda cx, cy, s, r, o: camel_shape(cx, cy, s, "#f4a261", o), ["#fff3e0", "#ffe4c2"], 5, (190, 270))),
    ("Pink Elephant Parade", scene(lambda cx, cy, s, r, o: elephant_shape(cx, cy, s, "#ffb3c6", o), ["#fff0f5", "#ffe6ee"], 5, (200, 280))),
    ("Spotted Giraffe Friends", scene(lambda cx, cy, s, r, o: giraffe_shape(cx, cy, s, "#ffd166", "#e76f51", o), ["#fff8e0", "#ffe9c2"], 5, (200, 300))),
    ("Purple Savanna Zebras", scene(lambda cx, cy, s, r, o: zebra_shape(cx, cy, s, o), ["#f3e8ff", "#e0d4ff"], 6, (180, 260))),
    ("Desert Night Cactus", scene(lambda cx, cy, s, r, o: cactus_shape(cx, cy, s, "#264653", o), ["#03071e", "#0a2540"], 6, (180, 260))),
    ("Two-Hump Camel Fun", scene(lambda cx, cy, s, r, o: camel_shape(cx, cy, s, "#d4a373", o), ["#eaf6ff", "#cdeffd"], 5, (190, 270))),
    ("Elephant & Friends Watering Hole", scene(lambda cx, cy, s, r, o: elephant_shape(cx, cy, s, "#6c757d", o), ["#d8f3dc", "#b7e4c7"], 5, (200, 280))),
    ("Rainbow Giraffe Spots", scene(lambda cx, cy, s, r, o: giraffe_shape(cx, cy, s, "#ffe066", "#9b5de5", o), ["#ff9fbf", "#9fd8ff"], 5, (200, 300))),
    ("Zebra Stripe Party", scene(lambda cx, cy, s, r, o: zebra_shape(cx, cy, s, o), ["#eafff1", "#d0f4de"], 6, (180, 260))),
])


# ---- Reptiles & Amphibians -----------------------------------------------------------

def frog_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        ellipse(cx, cy + 10 * s, 50 * s, 38 * s, fill, opacity),
        circle(cx - 25 * s, cy - 30 * s, 18 * s, fill, opacity),
        circle(cx + 25 * s, cy - 30 * s, 18 * s, fill, opacity),
        circle(cx - 25 * s, cy - 32 * s, 8 * s, "#1a1a1a", opacity),
        circle(cx + 25 * s, cy - 32 * s, 8 * s, "#1a1a1a", opacity),
        f'<path d="M {cx-20*s:.1f} {cy+15*s:.1f} Q {cx:.1f} {cy+28*s:.1f} {cx+20*s:.1f} {cy+15*s:.1f}" '
        f'fill="none" stroke="#1a1a1a" stroke-width="{3*s:.1f}" stroke-linecap="round" opacity="{opacity:.2f}"/>',
        ellipse(cx - 45 * s, cy + 35 * s, 16 * s, 10 * s, fill, opacity),
        ellipse(cx + 45 * s, cy + 35 * s, 16 * s, 10 * s, fill, opacity),
    ]
    return group(items)


def turtle_shape(cx, cy, size, shell_color, body_color, opacity=1):
    s = size / 100.0
    items = [
        ellipse(cx, cy, 55 * s, 45 * s, body_color, opacity),
        circle(cx, cy - 2 * s, 42 * s, shell_color, opacity),
        circle(cx - 16 * s, cy - 14 * s, 10 * s, shell_color, opacity * 0.6),
        circle(cx + 16 * s, cy - 14 * s, 10 * s, shell_color, opacity * 0.6),
        circle(cx, cy + 14 * s, 10 * s, shell_color, opacity * 0.6),
        circle(cx - 65 * s, cy - 5 * s, 16 * s, body_color, opacity),
        circle(cx - 70 * s, cy - 8 * s, 3 * s, "#1a1a1a", opacity),
    ]
    return group(items)


def chameleon_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        f'<path d="M {cx-50*s:.1f} {cy+10*s:.1f} Q {cx-20*s:.1f} {cy-40*s:.1f} {cx+30*s:.1f} {cy-10*s:.1f} '
        f'Q {cx+60*s:.1f} {cy+5*s:.1f} {cx+40*s:.1f} {cy+30*s:.1f} '
        f'Q {cx:.1f} {cy+45*s:.1f} {cx-50*s:.1f} {cy+10*s:.1f} Z" fill="{fill}" opacity="{opacity:.2f}"/>',
        circle(cx + 30 * s, cy - 15 * s, 14 * s, fill, opacity),
        circle(cx + 34 * s, cy - 18 * s, 6 * s, "#1a1a1a", opacity),
        f'<path d="M {cx-50*s:.1f} {cy+10*s:.1f} Q {cx-80*s:.1f} {cy-10*s:.1f} {cx-95*s:.1f} {cy+20*s:.1f}" '
        f'fill="none" stroke="{fill}" stroke-width="{10*s:.1f}" stroke-linecap="round" opacity="{opacity:.2f}"/>',
    ]
    return group(items)


def snake_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    d = f"M {cx-90*s} {cy} Q {cx-50*s} {cy-40*s} {cx-10*s} {cy} Q {cx+30*s} {cy+40*s} {cx+60*s} {cy}"
    items = [f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="{22*s:.1f}" stroke-linecap="round" '
             f'opacity="{opacity:.2f}"/>',
             circle(cx + 70 * s, cy - 5 * s, 16 * s, fill, opacity),
             circle(cx + 75 * s, cy - 10 * s, 4 * s, "#1a1a1a", opacity)]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("reptiles-amphibians", "Reptiles & Amphibians", [
    ("Leaping Green Frogs", scene(lambda cx, cy, s, r, o: frog_shape(cx, cy, s, "#52b788", o), ["#d8f3dc", "#b7e4c7"], 7, (150, 230))),
    ("Basking Turtle Friends", scene(lambda cx, cy, s, r, o: turtle_shape(cx, cy, s, "#2d6a4f", "#95d5b2", o), ["#eafff1", "#d0f4de"], 6, (170, 250))),
    ("Color-Changing Chameleon", scene(lambda cx, cy, s, r, o: chameleon_shape(cx, cy, s, "#06d6a0", o), ["#caf0f8", "#90e0ef"], 6, (160, 240))),
    ("Friendly Garden Snake", scene(lambda cx, cy, s, r, o: snake_shape(cx, cy, s, "#2a9d8f", o, r), ["#fff3e0", "#ffe4c2"], 6, (160, 240), True)),
    ("Blue Poison Frog", scene(lambda cx, cy, s, r, o: frog_shape(cx, cy, s, "#4361ee", o), ["#eaf6ff", "#cdeffd"], 7, (150, 230))),
    ("Sea Turtle Cove", scene(lambda cx, cy, s, r, o: turtle_shape(cx, cy, s, "#118ab2", "#4cc9f0", o), ["#00b4d8", "#90e0ef"], 6, (170, 250))),
    ("Rainbow Chameleon Mood", scene(lambda cx, cy, s, r, o: chameleon_shape(cx, cy, s, "#f15bb5", o), ["#ff9fbf", "#9fd8ff"], 6, (160, 240))),
    ("Striped Corn Snake", scene(lambda cx, cy, s, r, o: snake_shape(cx, cy, s, "#e76f51", o, r), ["#fff8e0", "#ffe9c2"], 6, (160, 240), True)),
    ("Tree Frog Hideaway", scene(lambda cx, cy, s, r, o: frog_shape(cx, cy, s, "#a3e635", o), ["#1b4332", "#2d6a4f"], 7, (150, 230))),
    ("Desert Tortoise Trail", scene(lambda cx, cy, s, r, o: turtle_shape(cx, cy, s, "#e9c46a", "#f4a261", o), ["#ffe8b0", "#ffcf8a"], 6, (170, 250))),
    ("Purple Chameleon Chill", scene(lambda cx, cy, s, r, o: chameleon_shape(cx, cy, s, "#9b5de5", o), ["#f3e8ff", "#e0d4ff"], 6, (160, 240))),
    ("Emerald Garden Snake", scene(lambda cx, cy, s, r, o: snake_shape(cx, cy, s, "#2d6a4f", o, r), ["#d8f3dc", "#b7e4c7"], 6, (160, 240), True)),
    ("Yellow Spotted Frog", scene(lambda cx, cy, s, r, o: frog_shape(cx, cy, s, "#ffd166", o), ["#fff3b0", "#ffe066"], 7, (150, 230))),
    ("Painted Turtle Pond", scene(lambda cx, cy, s, r, o: turtle_shape(cx, cy, s, "#e63946", "#f4a261", o), ["#eafff1", "#d0f4de"], 6, (170, 250))),
    ("Sunset Chameleon Branch", scene(lambda cx, cy, s, r, o: chameleon_shape(cx, cy, s, "#ff9f1c", o), ["#ff9f7b", "#ff6f91"], 6, (160, 240))),
    ("Night Garden Snake", scene(lambda cx, cy, s, r, o: snake_shape(cx, cy, s, "#3a0ca3", o, r), ["#03071e", "#0a2540"], 6, (160, 240), True)),
    ("Pink Poison Dart Frog", scene(lambda cx, cy, s, r, o: frog_shape(cx, cy, s, "#f15bb5", o), ["#fff0f5", "#ffe6ee"], 7, (150, 230))),
    ("Galapagos Giant Turtle", scene(lambda cx, cy, s, r, o: turtle_shape(cx, cy, s, "#6b4423", "#8a5a2b", o), ["#f0ead2", "#e4d9b8"], 6, (170, 250))),
    ("Teal Chameleon Calm", scene(lambda cx, cy, s, r, o: chameleon_shape(cx, cy, s, "#2ec4b6", o), ["#e0f7fa", "#b2ebf2"], 6, (160, 240))),
    ("Golden Garden Snake", scene(lambda cx, cy, s, r, o: snake_shape(cx, cy, s, "#ffd166", o, r), ["#fff8e0", "#ffefc2"], 6, (160, 240), True)),
])


# ---- Emojis & Smiley Faces -----------------------------------------------------------

def smiley_shape(cx, cy, size, face_color, mood, opacity=1):
    s = size / 100.0
    items = [circle(cx, cy, 55 * s, face_color, opacity)]
    if mood == "sunglasses":
        items.append(rect(cx - 40 * s, cy - 12 * s, 34 * s, 20 * s, "#1a1a1a", rx=6 * s, opacity=opacity))
        items.append(rect(cx + 6 * s, cy - 12 * s, 34 * s, 20 * s, "#1a1a1a", rx=6 * s, opacity=opacity))
        items.append(line(cx - 6 * s, cy - 4 * s, cx + 6 * s, cy - 4 * s, "#1a1a1a", 4 * s, opacity))
    elif mood == "heart":
        items.append(heart_shape(cx - 20 * s, cy - 10 * s, 26, "#e63946", opacity))
        items.append(heart_shape(cx + 20 * s, cy - 10 * s, 26, "#e63946", opacity))
    elif mood == "wink":
        items.append(circle(cx - 20 * s, cy - 8 * s, 8 * s, "#1a1a1a", opacity))
        items.append(line(cx + 12 * s, cy - 8 * s, cx + 28 * s, cy - 8 * s, "#1a1a1a", 4 * s, opacity))
    elif mood == "star":
        items.append(star_shape(cx - 20 * s, cy - 8 * s, 12 * s, "#ffd166", 5, 0, opacity))
        items.append(star_shape(cx + 20 * s, cy - 8 * s, 12 * s, "#ffd166", 5, 0, opacity))
    else:  # happy / laugh
        items.append(circle(cx - 20 * s, cy - 8 * s, 8 * s, "#1a1a1a", opacity))
        items.append(circle(cx + 20 * s, cy - 8 * s, 8 * s, "#1a1a1a", opacity))
    if mood != "sunglasses":
        items.append(f'<path d="M {cx-26*s:.1f} {cy+15*s:.1f} Q {cx:.1f} {cy+42*s:.1f} {cx+26*s:.1f} {cy+15*s:.1f}" '
                     f'fill="none" stroke="#1a1a1a" stroke-width="{5*s:.1f}" stroke-linecap="round" '
                     f'opacity="{opacity:.2f}"/>')
    else:
        items.append(f'<path d="M {cx-20*s:.1f} {cy+20*s:.1f} Q {cx:.1f} {cy+34*s:.1f} {cx+20*s:.1f} {cy+20*s:.1f}" '
                     f'fill="none" stroke="#1a1a1a" stroke-width="{5*s:.1f}" stroke-linecap="round" '
                     f'opacity="{opacity:.2f}"/>')
    return group(items)


MOODS = ["happy", "wink", "sunglasses", "heart", "star"]


cat("emoji-faces", "Emojis & Smiley Faces", [
    ("Happy Face Party", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ffd166", "happy", o), ["#fff8e0", "#ffefc2"], 8, (140, 220))),
    ("Cool Sunglasses Squad", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ffd166", "sunglasses", o), ["#00b4d8", "#90e0ef"], 8, (140, 220))),
    ("Heart Eyes Everywhere", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ff8fa3", "heart", o), ["#fff0f5", "#ffe6ee"], 8, (140, 220))),
    ("Winking Smiley Fun", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ffd166", "wink", o), ["#eafff1", "#d0f4de"], 8, (140, 220))),
    ("Star Struck Smiles", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ffd166", "star", o), ["#3a0ca3", "#7209b7"], 8, (140, 220))),
    ("Pink Happy Faces", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ff9fd6", "happy", o), ["#fdf0ff", "#ffe6f7"], 8, (140, 220))),
    ("Blue Sunglasses Vibes", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#4cc9f0", "sunglasses", o), ["#eaf6ff", "#cdeffd"], 8, (140, 220))),
    ("Rainbow Heart Eyes", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, rng_choice_colors(r), "heart", o), ["#ff9fbf", "#9fd8ff"], 8, (140, 220))),
    ("Green Winking Crew", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#95d5b2", "wink", o), ["#d8f3dc", "#b7e4c7"], 8, (140, 220))),
    ("Golden Star Smiles", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ffe066", "star", o), ["#fff3b0", "#ffe066"], 8, (140, 220))),
    ("Purple Happy Vibes", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#c8b6ff", "happy", o), ["#f3e8ff", "#e0d4ff"], 8, (140, 220))),
    ("Orange Sunglasses Cool", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#f4a261", "sunglasses", o), ["#fff3e0", "#ffe4c2"], 8, (140, 220))),
    ("Sweetheart Smiley Mix", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ff6f91", "heart", o), ["#ffe0ec", "#ffc2d9"], 8, (140, 220))),
    ("Playful Wink Party", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ffd166", "wink", o), ["#caf0f8", "#90e0ef"], 8, (140, 220))),
    ("Night Sky Star Smiles", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#c8b6ff", "star", o), ["#03071e", "#0a2540"], 8, (140, 220))),
    ("Sunny Yellow Grins", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ffe066", "happy", o), ["#fff8e0", "#ffefc2"], 8, (140, 220))),
    ("Teal Sunglasses Chill", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#2ec4b6", "sunglasses", o), ["#e0f7fa", "#b2ebf2"], 8, (140, 220))),
    ("Confetti Heart Eyes", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#ff9f1c", "heart", o), ["#ffe8b0", "#ffcf8a"], 8, (140, 220))),
    ("Silly Wink Squad", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, "#adb5bd", "wink", o), ["#e9ecef", "#ced4da"], 8, (140, 220))),
    ("All-Star Smiley Mix", scene(lambda cx, cy, s, r, o: smiley_shape(cx, cy, s, rng_choice_colors(r), "star", o), ["#eafff1", "#d0f4de"], 8, (140, 220))),
])


# ---- Board Games & Puzzles -----------------------------------------------------------

def die_shape(cx, cy, size, fill, dot_color, pips, opacity=1, rotation=0):
    s = size / 100.0
    items = [rect(cx - 45 * s, cy - 45 * s, 90 * s, 90 * s, fill, rx=16 * s, opacity=opacity)]
    layouts = {
        1: [(0, 0)],
        2: [(-20, -20), (20, 20)],
        3: [(-20, -20), (0, 0), (20, 20)],
        4: [(-20, -20), (20, -20), (-20, 20), (20, 20)],
        5: [(-20, -20), (20, -20), (0, 0), (-20, 20), (20, 20)],
        6: [(-20, -22), (20, -22), (-20, 0), (20, 0), (-20, 22), (20, 22)],
    }
    for dx, dy in layouts.get(pips, [(0, 0)]):
        items.append(circle(cx + dx * s, cy + dy * s, 7 * s, dot_color, opacity))
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def card_shape(cx, cy, size, fill, suit_color, suit, opacity=1, rotation=0):
    s = size / 100.0
    items = [rect(cx - 40 * s, cy - 55 * s, 80 * s, 110 * s, fill, rx=10 * s, opacity=opacity)]
    if suit == "heart":
        items.append(heart_shape(cx, cy, 45, suit_color, opacity))
    elif suit == "star":
        items.append(star_shape(cx, cy, 32 * s, suit_color, 5, 0, opacity))
    else:  # circle / token suit
        items.append(circle(cx, cy, 26 * s, suit_color, opacity))
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def puzzle_piece_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        rect(cx - 45 * s, cy - 45 * s, 90 * s, 90 * s, fill, rx=10 * s, opacity=opacity),
        circle(cx + 45 * s, cy, 18 * s, fill, opacity),
        circle(cx, cy - 45 * s, 18 * s, fill, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("board-games-puzzles", "Board Games & Puzzles", [
    ("Rolling Dice Fun", scene(lambda cx, cy, s, r, o: die_shape(cx, cy, s, "#ffffff", "#e63946", (int(abs(r))%6)+1, o, r), ["#ff9fbf", "#9fd8ff"], 8, (130, 210), True)),
    ("Puzzle Piece Puzzle", scene(lambda cx, cy, s, r, o: puzzle_piece_shape(cx, cy, s, rng_choice_colors(r), o, r), ["#eaf6ff", "#cdeffd"], 8, (120, 200), True)),
    ("Playing Card Hearts", scene(lambda cx, cy, s, r, o: card_shape(cx, cy, s, "#ffffff", "#e63946", "heart", o, r), ["#fff0f5", "#ffe6ee"], 6, (170, 250), True)),
    ("Star Token Game Night", scene(lambda cx, cy, s, r, o: card_shape(cx, cy, s, "#ffffff", "#ffd166", "star", o, r), ["#fff8e0", "#ffe9c2"], 6, (170, 250), True)),
    ("Colorful Dice Roll", scene(lambda cx, cy, s, r, o: die_shape(cx, cy, s, rng_choice_colors(r), "#ffffff", (int(abs(r))%6)+1, o, r), ["#eafff1", "#d0f4de"], 8, (130, 210), True)),
    ("Rainbow Puzzle Pieces", scene(lambda cx, cy, s, r, o: puzzle_piece_shape(cx, cy, s, rng_choice_colors(r), o, r), ["#fdf0ff", "#ffe6f7"], 8, (120, 200), True)),
    ("Blue Card Deck", scene(lambda cx, cy, s, r, o: card_shape(cx, cy, s, "#ffffff", "#4361ee", "circle", o, r), ["#caf0f8", "#90e0ef"], 6, (170, 250), True)),
    ("Golden Dice Party", scene(lambda cx, cy, s, r, o: die_shape(cx, cy, s, "#fff3b0", "#e63946", (int(abs(r))%6)+1, o, r), ["#ffe8b0", "#ffcf8a"], 8, (130, 210), True)),
    ("Jigsaw Adventure", scene(lambda cx, cy, s, r, o: puzzle_piece_shape(cx, cy, s, rng_choice_colors(r), o, r), ["#f3e8ff", "#e0d4ff"], 8, (120, 200), True)),
    ("Heart Card Game", scene(lambda cx, cy, s, r, o: card_shape(cx, cy, s, "#ffffff", "#ff8fa3", "heart", o, r), ["#ffe0ec", "#ffc2d9"], 6, (170, 250), True)),
    ("Purple Dice Tumble", scene(lambda cx, cy, s, r, o: die_shape(cx, cy, s, "#e0d4ff", "#7209b7", (int(abs(r))%6)+1, o, r), ["#3a0ca3", "#7209b7"], 8, (130, 210), True)),
    ("Puzzle Time Together", scene(lambda cx, cy, s, r, o: puzzle_piece_shape(cx, cy, s, rng_choice_colors(r), o, r), ["#d8f3dc", "#b7e4c7"], 8, (120, 200), True)),
    ("Star Card Shuffle", scene(lambda cx, cy, s, r, o: card_shape(cx, cy, s, "#ffffff", "#118ab2", "star", o, r), ["#a8e6ff", "#dff7ff"], 6, (170, 250), True)),
    ("Neon Dice Night", scene(lambda cx, cy, s, r, o: die_shape(cx, cy, s, "#212529", "#00f5d4", (int(abs(r))%6)+1, o, r), ["#0d0221", "#190535"], 8, (130, 210), True)),
    ("Sunny Puzzle Pieces", scene(lambda cx, cy, s, r, o: puzzle_piece_shape(cx, cy, s, rng_choice_colors(r), o, r), ["#fff8e0", "#ffefc2"], 8, (120, 200), True)),
    ("Circle Token Card Game", scene(lambda cx, cy, s, r, o: card_shape(cx, cy, s, "#ffffff", "#06d6a0", "circle", o, r), ["#eafff1", "#d0f4de"], 6, (170, 250), True)),
    ("Cotton Candy Dice", scene(lambda cx, cy, s, r, o: die_shape(cx, cy, s, "#ffe0ec", "#f15bb5", (int(abs(r))%6)+1, o, r), ["#ffb3c6", "#c8b6ff"], 8, (130, 210), True)),
    ("Family Puzzle Night", scene(lambda cx, cy, s, r, o: puzzle_piece_shape(cx, cy, s, rng_choice_colors(r), o, r), ["#e0f7fa", "#b2ebf2"], 8, (120, 200), True)),
    ("Heart & Star Card Mix", scene(lambda cx, cy, s, r, o: card_shape(cx, cy, s, "#ffffff", "#9b5de5", "star", o, r), ["#f0ead2", "#e4d9b8"], 6, (170, 250), True)),
    ("Game Night Dice Duo", scene(lambda cx, cy, s, r, o: die_shape(cx, cy, s, "#ffffff", "#2b2b2b", (int(abs(r))%6)+1, o, r), ["#f8f9fa", "#dee2e6"], 8, (130, 210), True)),
])


# ============================================================================
# SECOND EXPANSION PACK -- 16 more illustrated categories, 25 variants each
# (400 backgrounds), to grow the library toward 1000 and add a lot more tabs.
# ============================================================================

def titled_variants(seed, moods, palette_options, sky_options, factory, count=25, name=""):
    """Deterministically builds `count` (title, builder) tuples by combining
    moods x palettes x skies, keeping titles unique. `factory(colors, sky)`
    must return a build(svg, rng) function -- typically `scene(...)`."""
    rng_local = random.Random(seed)
    combos = [(m, p, s) for m in moods for p in palette_options for s in sky_options]
    rng_local.shuffle(combos)
    seen = set()
    out = []
    for mood, (pname, pcolors), (sname, scolors) in combos:
        title = f"{mood} {pname} {name}".replace("  ", " ").strip()
        if title in seen:
            continue
        seen.add(title)
        out.append((title, factory(pcolors, scolors)))
        if len(out) >= count:
            break
    if len(out) < count:
        raise ValueError(f"titled_variants({seed!r}): only {len(out)}/{count} unique titles")
    return out


def multi_kind_scene(shape_fn, kinds, colors, sky, count=6, size_range=(170, 260), angle=100):
    """Like scene(), but shape_fn(cx, cy, size, colors, kind, opacity) picks a
    random `kind` per instance via the real rng (kind varies breed/species)."""
    def build(svg, rng):
        grad_bg(svg, sky, angle)
        scatter(svg, rng, lambda cx, cy, s, r, o: shape_fn(cx, cy, s, colors, rng.choice(kinds), o),
                count, size_range=size_range, rotate=True)
    return build


# ---- Dogs & Puppies ---------------------------------------------------------

def dog_breed_shape(cx, cy, size, colors, kind, opacity=1):
    coat, accent = colors[0], (colors[1] if len(colors) > 1 else colors[0])
    s = size / 100.0
    items = []
    if kind == "labrador":
        items.append(ellipse(cx - 50 * s, cy - 10 * s, 16 * s, 34 * s, coat, opacity, transform=f"rotate(10 {cx-50*s} {cy-10*s})"))
        items.append(ellipse(cx + 50 * s, cy - 10 * s, 16 * s, 34 * s, coat, opacity, transform=f"rotate(-10 {cx+50*s} {cy-10*s})"))
    elif kind == "poodle":
        items.append(cloud_shape(cx, cy - 8 * s, size * 0.75, coat, opacity))
    elif kind == "corgi":
        items.append(polygon([(cx-60*s, cy-40*s), (cx-30*s, cy-40*s), (cx-45*s, cy-85*s)], coat, opacity))
        items.append(polygon([(cx+60*s, cy-40*s), (cx+30*s, cy-40*s), (cx+45*s, cy-85*s)], coat, opacity))
    elif kind == "beagle":
        items.append(ellipse(cx - 55 * s, cy, 18 * s, 40 * s, accent, opacity, transform=f"rotate(8 {cx-55*s} {cy})"))
        items.append(ellipse(cx + 55 * s, cy, 18 * s, 40 * s, accent, opacity, transform=f"rotate(-8 {cx+55*s} {cy})"))
    else:  # pug
        items.append(ellipse(cx - 45 * s, cy - 35 * s, 14 * s, 18 * s, coat, opacity))
        items.append(ellipse(cx + 45 * s, cy - 35 * s, 14 * s, 18 * s, coat, opacity))
    items.append(circle(cx, cy, 60 * s, coat, opacity))
    if kind == "beagle":
        items.append(f'<path d="M {cx-60*s:.1f} {cy-10*s:.1f} A {60*s:.1f} {60*s:.1f} 0 0 1 {cx+10*s:.1f} {cy-58*s:.1f} '
                     f'L {cx-10*s:.1f} {cy-20*s:.1f} Z" fill="{accent}" opacity="{opacity:.2f}"/>')
    items.append(circle(cx - 22 * s, cy - 5 * s, 8 * s, "#2b2b2b", opacity))
    items.append(circle(cx + 22 * s, cy - 5 * s, 8 * s, "#2b2b2b", opacity))
    items.append(ellipse(cx, cy + 20 * s, 12 * s, 9 * s, "#2b2b2b", opacity))
    if kind == "pug":
        items.append(f'<path d="M {cx-14*s:.1f} {cy+28*s:.1f} Q {cx:.1f} {cy+20*s:.1f} {cx+14*s:.1f} {cy+28*s:.1f}" '
                     f'fill="none" stroke="#5b4636" stroke-width="{3*s:.1f}" opacity="{opacity:.2f}"/>')
    return group(items)


DOG_KINDS = ["labrador", "poodle", "corgi", "beagle", "pug"]

cat("dogs-puppies", "Dogs & Puppies", titled_variants(
    "dogs-puppies",
    moods=["Playful", "Sleepy", "Happy", "Curious", "Loyal", "Cheerful", "Bouncy"],
    palette_options=[
        ("Golden", ["#e8b84b", "#f4d78a"]), ("Chocolate", ["#6b4423", "#8a5a2b"]),
        ("Black & White", ["#2b2b2b", "#f4f1ea"]), ("Cream", ["#f4ecd8", "#e8dcc0"]),
    ],
    sky_options=[("in the Park", ["#d8f3dc", "#b7e4c7"]), ("at Home", ["#fff3e0", "#ffe4c2"]),
                 ("on a Walk", ["#eaf6ff", "#cdeffd"])],
    factory=lambda colors, sky: multi_kind_scene(dog_breed_shape, DOG_KINDS, colors, sky, 6, (170, 250)),
    name="Pup",
))

# ---- Horses & Ponies ---------------------------------------------------------

def horse_shape(cx, cy, size, colors, opacity=1):
    coat, mane = colors[0], (colors[1] if len(colors) > 1 else "#3a2a1a")
    s = size / 100.0
    items = [
        ellipse(cx, cy + 15 * s, 45 * s, 55 * s, coat, opacity),
        ellipse(cx, cy + 60 * s, 22 * s, 30 * s, coat, opacity),
        polygon([(cx-35*s, cy-35*s), (cx-15*s, cy-35*s), (cx-25*s, cy-70*s)], coat, opacity),
        polygon([(cx+35*s, cy-35*s), (cx+15*s, cy-35*s), (cx+25*s, cy-70*s)], coat, opacity),
        circle(cx - 18 * s, cy + 5 * s, 7 * s, "#2b2b2b", opacity),
        circle(cx + 18 * s, cy + 5 * s, 7 * s, "#2b2b2b", opacity),
        ellipse(cx, cy + 80 * s, 9 * s, 6 * s, "#3a2a1a", opacity),
    ]
    for i in range(5):
        mx, my = cx - 38 * s + i * 4 * s, cy - 40 * s + i * 14 * s
        items.append(ellipse(mx, my, 9 * s, 16 * s, mane, opacity * 0.9, transform=f"rotate(-20 {mx} {my})"))
    return group(items)


cat("horses-ponies", "Horses & Ponies", titled_variants(
    "horses-ponies",
    moods=["Galloping", "Gentle", "Spirited", "Sweet", "Majestic", "Trotting", "Dreamy"],
    palette_options=[
        ("Chestnut", ["#8a5a2b", "#3a2a1a"]), ("Palomino", ["#e8c88a", "#fff3e0"]),
        ("Dapple Grey", ["#adb5bd", "#495057"]), ("Black Stallion", ["#212529", "#495057"]),
    ],
    sky_options=[("Pony", ["#eafff1", "#d0f4de"]), ("Meadow Horse", ["#fff3e0", "#ffe4c2"]),
                 ("Sunset Horse", ["#ff9f7b", "#ff6f91"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: horse_shape(cx, cy, s, colors, o), sky, 5, (200, 300)),
    name="",
))

# ---- Ballet & Dance -----------------------------------------------------------

def tutu_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        circle(cx, cy - 70 * s, 22 * s, "#ffe0c2", opacity),
        f'<path d="M {cx-70*s:.1f} {cy+50*s:.1f} Q {cx:.1f} {cy-10*s:.1f} {cx+70*s:.1f} {cy+50*s:.1f} '
        f'Q {cx:.1f} {cy+30*s:.1f} {cx-70*s:.1f} {cy+50*s:.1f} Z" fill="{fill}" opacity="{opacity:.2f}"/>',
        rect(cx - 8 * s, cy - 48 * s, 16 * s, 45 * s, "#ffe0c2", opacity=opacity),
    ]
    return group(items)


def ballet_shoe_shape(cx, cy, size, fill, ribbon_color, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        f'<path d="M {cx-40*s:.1f} {cy:.1f} C {cx-45*s:.1f} {cy-30*s:.1f}, {cx-10*s:.1f} {cy-38*s:.1f}, {cx+15*s:.1f} {cy-25*s:.1f} '
        f'C {cx+40*s:.1f} {cy-15*s:.1f}, {cx+45*s:.1f} {cy+15*s:.1f}, {cx+35*s:.1f} {cy+22*s:.1f} '
        f'C {cx+10*s:.1f} {cy+30*s:.1f}, {cx-35*s:.1f} {cy+22*s:.1f}, {cx-40*s:.1f} {cy:.1f} Z" fill="{fill}" opacity="{opacity:.2f}"/>',
        line(cx + 10 * s, cy + 15 * s, cx + 40 * s, cy + 70 * s, ribbon_color, 5 * s, opacity),
        line(cx - 5 * s, cy + 18 * s, cx - 25 * s, cy + 75 * s, ribbon_color, 5 * s, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("ballet-dance", "Ballet & Dance", titled_variants(
    "ballet-dance",
    moods=["Graceful", "Twirling", "Elegant", "Dreamy", "Sparkling", "Center Stage", "Prima"],
    palette_options=[("Pink", ["#ff8fa3", "#ffd6e8"]), ("Lavender", ["#c8b6ff", "#e0d4ff"]),
                      ("Sky Blue", ["#a6e3ff", "#caf0f8"]), ("Sunshine", ["#ffe066", "#fff3b0"])],
    sky_options=[("Ballerina", ["#fff0f5", "#ffe6ee"]), ("Stage Lights", ["#2b2d42", "#3a0ca3"]),
                 ("Studio", ["#f3e8ff", "#eae4ff"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: tutu_shape(cx, cy, s, colors[0], o), sky, 5, (200, 300)),
    name="Ballerina",
))

# ---- Autumn & Fall -------------------------------------------------------------

def leaf_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    d = f"M {cx} {cy-60*s} C {cx+40*s} {cy-40*s}, {cx+40*s} {cy+30*s}, {cx} {cy+60*s} C {cx-40*s} {cy+30*s}, {cx-40*s} {cy-40*s}, {cx} {cy-60*s} Z"
    items = [path(d, fill, opacity), line(cx, cy - 55 * s, cx, cy + 55 * s, "#6b4423", 2 * s, opacity * 0.6)]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def pumpkin_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = []
    for dx in (-30, -10, 10, 30):
        items.append(ellipse(cx + dx * s, cy + 10 * s, 22 * s, 45 * s, fill, opacity))
    items.append(rect(cx - 6 * s, cy - 45 * s, 12 * s, 25 * s, "#6b8e23", rx=4 * s, opacity=opacity))
    return group(items)


cat("autumn-fall", "Autumn & Fall", titled_variants(
    "autumn-fall",
    moods=["Crisp", "Cozy", "Golden", "Falling", "Harvest", "Rustling", "Amber"],
    palette_options=[("Red Leaf", ["#e63946"]), ("Orange Leaf", ["#f4a261"]),
                      ("Golden Leaf", ["#ffb703"]), ("Brown Leaf", ["#8a5a2b"])],
    sky_options=[("Autumn Sky", ["#ffe8b0", "#ffcf8a"]), ("Harvest Morning", ["#fff3e0", "#ffe4c2"]),
                 ("Fall Dusk", ["#ff9f7b", "#ff6f91"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: leaf_shape(cx, cy, s, colors[0], o, r), sky, 16, (70, 150), True),
    name="Leaves",
))

# ---- Spring & Garden -----------------------------------------------------------

def tulip_shape(cx, cy, size, fill, opacity=1):
    s = size / 100.0
    items = [
        f'<path d="M {cx-20*s:.1f} {cy:.1f} C {cx-25*s:.1f} {cy-40*s:.1f}, {cx-10*s:.1f} {cy-55*s:.1f}, {cx:.1f} {cy-55*s:.1f} '
        f'C {cx+10*s:.1f} {cy-55*s:.1f}, {cx+25*s:.1f} {cy-40*s:.1f}, {cx+20*s:.1f} {cy:.1f} '
        f'C {cx+10*s:.1f} {cy-10*s:.1f}, {cx-10*s:.1f} {cy-10*s:.1f}, {cx-20*s:.1f} {cy:.1f} Z" fill="{fill}" opacity="{opacity:.2f}"/>',
        line(cx, cy, cx, cy + 70 * s, "#2d6a4f", 5 * s, opacity),
        ellipse(cx - 15 * s, cy + 40 * s, 14 * s, 6 * s, "#2d6a4f", opacity, transform=f"rotate(-30 {cx-15*s} {cy+40*s})"),
    ]
    return group(items)


cat("spring-garden", "Spring & Garden", titled_variants(
    "spring-garden",
    moods=["Blooming", "Fresh", "Sunny", "Budding", "Cheerful", "Dewy", "New"],
    palette_options=[("Tulip", ["#e63946"]), ("Daffodil", ["#ffd60a"]), ("Violet", ["#9b5de5"]),
                      ("Pink Blossom", ["#ff8fa3"])],
    sky_options=[("Garden", ["#eafff1", "#d0f4de"]), ("Morning", ["#fff8e0", "#ffefc2"]),
                 ("Spring Sky", ["#dbe9ff", "#a8c6ff"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: tulip_shape(cx, cy, s, colors[0], o), sky, 12, (100, 180)),
    name="Garden",
))

# ---- Dragons & Mythical --------------------------------------------------------

def dragon_shape(cx, cy, size, colors, opacity=1, rotation=0):
    fill, wing = colors[0], (colors[1] if len(colors) > 1 else colors[0])
    s = size / 100.0
    items = [
        ellipse(cx, cy + 20 * s, 55 * s, 35 * s, fill, opacity),
        circle(cx - 60 * s, cy - 15 * s, 30 * s, fill, opacity),
        polygon([(cx-75*s, cy-35*s), (cx-65*s, cy-35*s), (cx-70*s, cy-55*s)], fill, opacity),
        polygon([(cx-55*s, cy-38*s), (cx-45*s, cy-38*s), (cx-50*s, cy-58*s)], fill, opacity),
        circle(cx - 68 * s, cy - 18 * s, 4 * s, "#ffe066", opacity),
        f'<path d="M {cx-10*s:.1f} {cy-5*s:.1f} Q {cx+50*s:.1f} {cy-70*s:.1f} {cx+90*s:.1f} {cy-20*s:.1f} '
        f'Q {cx+40*s:.1f} {cy-30*s:.1f} {cx+10*s:.1f} {cy+10*s:.1f} Z" fill="{wing}" opacity="{opacity*0.9:.2f}"/>',
        f'<path d="M {cx+40*s:.1f} {cy+40*s:.1f} Q {cx+90*s:.1f} {cy+60*s:.1f} {cx+100*s:.1f} {cy+100*s:.1f}" '
        f'fill="none" stroke="{fill}" stroke-width="{16*s:.1f}" stroke-linecap="round" opacity="{opacity:.2f}"/>',
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("dragons-mythical", "Dragons & Mythical", titled_variants(
    "dragons-mythical",
    moods=["Fierce", "Friendly", "Soaring", "Legendary", "Sparkling", "Mighty", "Ancient"],
    palette_options=[("Emerald", ["#2d6a4f", "#95d5b2"]), ("Ruby", ["#e63946", "#ff8fa3"]),
                      ("Sapphire", ["#118ab2", "#4cc9f0"]), ("Amethyst", ["#7209b7", "#c8b6ff"])],
    sky_options=[("Dragon Sky", ["#0d1b4c", "#1a1a40"]), ("Mountain Peak", ["#e0c3fc", "#8ec5fc"]),
                 ("Sunset Flight", ["#ff9f7b", "#ff6f91"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: dragon_shape(cx, cy, s, colors, o, r), sky, 4, (240, 340), True),
    name="Dragon",
))

# ---- Wizards & Magic School -----------------------------------------------------

def wizard_hat_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        polygon([(cx-45*s, cy+30*s), (cx+45*s, cy+30*s), (cx+8*s, cy-90*s)], fill, opacity),
        ellipse(cx, cy + 30 * s, 55 * s, 14 * s, fill, opacity),
        star_shape(cx + 8 * s, cy - 90 * s, 10 * s, "#ffd166", 5, 0, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


def wand_shape(cx, cy, size, fill, opacity=1, rotation=0):
    s = size / 100.0
    items = [
        line(cx - 40 * s, cy + 40 * s, cx + 40 * s, cy - 40 * s, "#6b4423", 6 * s, opacity),
        star_shape(cx + 45 * s, cy - 45 * s, 16 * s, fill, 5, 0, opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("wizards-magic", "Wizards & Magic School", titled_variants(
    "wizards-magic",
    moods=["Enchanted", "Mystical", "Starlit", "Spellbound", "Wise", "Glowing", "Secret"],
    palette_options=[("Purple", ["#7209b7"]), ("Midnight Blue", ["#023e8a"]),
                      ("Emerald", ["#2d6a4f"]), ("Golden", ["#ffd166"])],
    sky_options=[("Magic School", ["#0f0c29", "#302b63"]), ("Spell Study", ["#3a0ca3", "#7209b7"]),
                 ("Starry Tower", ["#1a1a40", "#0d1b4c"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: wizard_hat_shape(cx, cy, s, colors[0], o, r), sky, 6, (150, 230), True),
    name="Wizard Hat",
))

# ---- Treehouses & Forts -----------------------------------------------------------

def treehouse_shape(cx, cy, size, colors, opacity=1):
    wood, leaf = colors[0], (colors[1] if len(colors) > 1 else "#52b788")
    s = size / 100.0
    items = [
        rect(cx - 10 * s, cy - 20 * s, 20 * s, 140 * s, "#6b4423", opacity=opacity),
        circle(cx, cy - 60 * s, 70 * s, leaf, opacity * 0.9),
        rect(cx - 55 * s, cy + 20 * s, 110 * s, 45 * s, wood, rx=6 * s, opacity=opacity),
        polygon([(cx-60*s, cy+20*s), (cx+60*s, cy+20*s), (cx, cy-15*s)], "#8a5a2b", opacity),
        rect(cx - 8 * s, cy + 65 * s, 6 * s, 12 * s, wood, opacity=opacity),
        rect(cx + 2 * s, cy + 65 * s, 6 * s, 12 * s, wood, opacity=opacity),
    ]
    return group(items)


cat("treehouses-forts", "Treehouses & Forts", titled_variants(
    "treehouses-forts",
    moods=["Cozy", "Secret", "Adventure", "Hidden", "Sunny", "Woodland", "Magical"],
    palette_options=[("Oak", ["#8a5a2b", "#52b788"]), ("Autumn", ["#a0522d", "#e76f51"]),
                      ("Birch", ["#d4a373", "#95d5b2"]), ("Cedar", ["#6b4423", "#2d6a4f"])],
    sky_options=[("Treehouse", ["#d8f3dc", "#b7e4c7"]), ("Fort Sunset", ["#ff9f7b", "#ffcf8a"]),
                 ("Forest Fort", ["#eaf6ff", "#cdeffd"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: treehouse_shape(cx, cy, s, colors, o), sky, 4, (260, 360)),
    name="Treehouse",
))

# ---- Roller Skating & Scooters -----------------------------------------------------

def roller_skate_shape(cx, cy, size, colors, opacity=1, rotation=0):
    fill = colors[0]
    s = size / 100.0
    items = [
        f'<path d="M {cx-40*s:.1f} {cy:.1f} C {cx-45*s:.1f} {cy-25*s:.1f}, {cx-10*s:.1f} {cy-35*s:.1f}, {cx+20*s:.1f} {cy-20*s:.1f} '
        f'C {cx+40*s:.1f} {cy-10*s:.1f}, {cx+45*s:.1f} {cy+10*s:.1f}, {cx+35*s:.1f} {cy+18*s:.1f} '
        f'L {cx-38*s:.1f} {cy+18*s:.1f} Z" fill="{fill}" opacity="{opacity:.2f}"/>',
        circle(cx - 25 * s, cy + 26 * s, 8 * s, "#2b2b2b", opacity),
        circle(cx - 5 * s, cy + 26 * s, 8 * s, "#2b2b2b", opacity),
        circle(cx + 15 * s, cy + 26 * s, 8 * s, "#2b2b2b", opacity),
        circle(cx + 30 * s, cy + 26 * s, 8 * s, "#2b2b2b", opacity),
    ]
    t = f"rotate({rotation} {cx} {cy})" if rotation else None
    return group(items, transform=t)


cat("roller-skating", "Roller Skating & Scooters", titled_variants(
    "roller-skating",
    moods=["Speedy", "Retro", "Rolling", "Sunny Day", "Neon", "Sidewalk", "Weekend"],
    palette_options=[("Hot Pink", ["#ff5c8a"]), ("Electric Blue", ["#4cc9f0"]),
                      ("Sunshine Yellow", ["#ffd166"]), ("Lime", ["#a3e635"])],
    sky_options=[("Skate Park", ["#eaf6ff", "#cdeffd"]), ("Boardwalk", ["#fff3e0", "#ffe4c2"]),
                 ("Neon Rink", ["#3a0ca3", "#7209b7"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: roller_skate_shape(cx, cy, s, colors, o, r), sky, 8, (130, 210), True),
    name="Skates",
))

# ---- Baking & Kitchen -----------------------------------------------------------

def cookie_shape(cx, cy, size, colors, opacity=1):
    fill, chip = colors[0], (colors[1] if len(colors) > 1 else "#6b4423")
    s = size / 100.0
    items = [circle(cx, cy, 45 * s, fill, opacity)]
    for i in range(6):
        rad = math.radians(i * 60)
        items.append(circle(cx + 28 * s * math.cos(rad), cy + 28 * s * math.sin(rad), 6 * s, chip, opacity))
    return group(items)


def mixing_bowl_shape(cx, cy, size, colors, opacity=1):
    fill = colors[0]
    s = size / 100.0
    items = [
        f'<path d="M {cx-55*s:.1f} {cy-10*s:.1f} A {55*s:.1f} {45*s:.1f} 0 0 0 {cx+55*s:.1f} {cy-10*s:.1f} Z" fill="{fill}" opacity="{opacity:.2f}"/>',
        ellipse(cx, cy - 10 * s, 55 * s, 12 * s, fill, opacity),
    ]
    return group(items)


cat("baking-kitchen", "Baking & Kitchen", titled_variants(
    "baking-kitchen",
    moods=["Fresh-Baked", "Sweet", "Homemade", "Warm", "Sugary", "Kitchen", "Delicious"],
    palette_options=[("Chocolate Chip", ["#e8b84b", "#6b4423"]), ("Sugar Cookie", ["#fff3e0", "#ffd166"]),
                      ("Gingerbread", ["#8a5a2b", "#e63946"]), ("Pink Frosted", ["#ffd6e8", "#ff8fa3"])],
    sky_options=[("Bakery", ["#fff0f5", "#ffe6ee"]), ("Cozy Kitchen", ["#fff8e0", "#ffefc2"]),
                 ("Sunday Baking", ["#eafff1", "#d0f4de"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: cookie_shape(cx, cy, s, colors, o), sky, 8, (120, 200)),
    name="Cookies",
))

# ---- Hiking & Nature Trails -----------------------------------------------------

def binoculars_shape(cx, cy, size, colors, opacity=1):
    fill = colors[0]
    s = size / 100.0
    items = [
        circle(cx - 25 * s, cy, 22 * s, fill, opacity),
        circle(cx + 25 * s, cy, 22 * s, fill, opacity),
        rect(cx - 35 * s, cy - 15 * s, 70 * s, 22 * s, fill, rx=6 * s, opacity=opacity),
        circle(cx - 25 * s, cy, 12 * s, "#87ceeb", opacity),
        circle(cx + 25 * s, cy, 12 * s, "#87ceeb", opacity),
    ]
    return group(items)


cat("hiking-nature-trails", "Hiking & Nature Trails", titled_variants(
    "hiking-nature-trails",
    moods=["Scenic", "Adventurous", "Mountain", "Trailblazing", "Fresh Air", "Explorer's", "Peaceful"],
    palette_options=[("Forest Green", ["#2d6a4f"]), ("Trail Brown", ["#8a5a2b"]),
                      ("Sky Blue", ["#4cc9f0"]), ("Sunset Orange", ["#f4a261"])],
    sky_options=[("Mountain Trail", ["#e0c3fc", "#8ec5fc"]), ("Forest Path", ["#d8f3dc", "#b7e4c7"]),
                 ("Summit View", ["#ffe8b0", "#ffcf8a"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: binoculars_shape(cx, cy, s, colors, o), sky, 6, (150, 230)),
    name="Trail",
))

# ---- Tea Party -----------------------------------------------------------------

def teacup_shape(cx, cy, size, colors, opacity=1):
    fill, accent = colors[0], (colors[1] if len(colors) > 1 else "#ffffff")
    s = size / 100.0
    items = [
        f'<path d="M {cx-35*s:.1f} {cy-15*s:.1f} L {cx+35*s:.1f} {cy-15*s:.1f} L {cx+28*s:.1f} {cy+35*s:.1f} '
        f'C {cx+28*s:.1f} {cy+45*s:.1f}, {cx-28*s:.1f} {cy+45*s:.1f}, {cx-28*s:.1f} {cy+35*s:.1f} Z" fill="{fill}" opacity="{opacity:.2f}"/>',
        ellipse(cx, cy - 15 * s, 35 * s, 8 * s, accent, opacity),
        f'<path d="M {cx+28*s:.1f} {cy-5*s:.1f} Q {cx+55*s:.1f} {cy:.1f} {cx+28*s:.1f} {cy+20*s:.1f}" '
        f'fill="none" stroke="{fill}" stroke-width="{8*s:.1f}" opacity="{opacity:.2f}"/>',
    ]
    return group(items)


cat("tea-party", "Tea Party", titled_variants(
    "tea-party",
    moods=["Fancy", "Whimsical", "Dainty", "Garden", "Afternoon", "Vintage", "Delightful"],
    palette_options=[("Rose", ["#ff8fa3", "#ffe0eb"]), ("Lavender", ["#c8b6ff", "#f3e8ff"]),
                      ("Mint", ["#95d5b2", "#eafff1"]), ("Gold Rim", ["#ffd166", "#fff8e0"])],
    sky_options=[("Tea Garden", ["#fff0f5", "#ffe6ee"]), ("Sunny Porch", ["#fff8e0", "#ffefc2"]),
                 ("Lace Tablecloth", ["#f3e8ff", "#eae4ff"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: teacup_shape(cx, cy, s, colors, o), sky, 7, (140, 220)),
    name="Teacups",
))

# ---- Race Cars & Speed -----------------------------------------------------------

def race_car_shape(cx, cy, size, colors, opacity=1):
    body, stripe = colors[0], (colors[1] if len(colors) > 1 else "#ffffff")
    s = size / 100.0
    items = [
        polygon([(cx-90*s, cy+15*s), (cx-55*s, cy-30*s), (cx+50*s, cy-30*s), (cx+75*s, cy+15*s)], body, opacity),
        rect(cx - 95 * s, cy + 10 * s, 195 * s, 30 * s, body, rx=10 * s, opacity=opacity),
        rect(cx - 30 * s, cy - 45 * s, 60 * s, 15 * s, body, rx=4 * s, opacity=opacity),
        rect(cx - 20 * s, cy + 5 * s, 60 * s, 10 * s, stripe, opacity=opacity),
        circle(cx - 55 * s, cy + 50 * s, 20 * s, "#1a1a1a", opacity),
        circle(cx + 45 * s, cy + 50 * s, 20 * s, "#1a1a1a", opacity),
    ]
    return group(items)


cat("race-cars-speed", "Race Cars & Speed", titled_variants(
    "race-cars-speed",
    moods=["Turbo", "Fast", "Champion", "Roaring", "Track-Ready", "Victory Lap", "Nitro"],
    palette_options=[("Fire Red", ["#e63946", "#ffffff"]), ("Racing Blue", ["#4361ee", "#ffe066"]),
                      ("Neon Green", ["#39ff14", "#1a1a1a"]), ("Sunshine Yellow", ["#ffd166", "#1a1a1a"])],
    sky_options=[("Speedway", ["#adb5bd", "#495057"]), ("Sunset Track", ["#ff9f7b", "#ff6f91"]),
                 ("Finish Line", ["#eaf6ff", "#cdeffd"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: race_car_shape(cx, cy, s, colors, o), sky, 6, (170, 250)),
    name="Race Car",
))

# ---- Jungle & Rainforest -----------------------------------------------------------

def monkey_shape(cx, cy, size, colors, opacity=1):
    fur, face = colors[0], (colors[1] if len(colors) > 1 else "#f4c6a5")
    s = size / 100.0
    items = [
        circle(cx - 45 * s, cy - 25 * s, 18 * s, fur, opacity),
        circle(cx + 45 * s, cy - 25 * s, 18 * s, fur, opacity),
        circle(cx, cy, 55 * s, fur, opacity),
        circle(cx, cy + 5 * s, 38 * s, face, opacity),
        circle(cx - 16 * s, cy - 8 * s, 6 * s, "#1a1a1a", opacity),
        circle(cx + 16 * s, cy - 8 * s, 6 * s, "#1a1a1a", opacity),
        ellipse(cx, cy + 20 * s, 8 * s, 6 * s, "#1a1a1a", opacity),
    ]
    return group(items)


cat("jungle-rainforest", "Jungle & Rainforest", titled_variants(
    "jungle-rainforest",
    moods=["Wild", "Lush", "Tropical", "Swinging", "Misty", "Exotic", "Vibrant"],
    palette_options=[("Brown Monkey", ["#8a5a2b", "#f4c6a5"]), ("Golden Monkey", ["#e8b84b", "#fff3e0"]),
                      ("Grey Monkey", ["#6c757d", "#f4c6a5"]), ("Black Monkey", ["#2b2b2b", "#e8b88a"])],
    sky_options=[("Rainforest Canopy", ["#1b4332", "#2d6a4f"]), ("Jungle Mist", ["#d8f3dc", "#b7e4c7"]),
                 ("Tropical Dusk", ["#ff9f7b", "#ff6f91"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: monkey_shape(cx, cy, s, colors, o), sky, 5, (190, 270)),
    name="Monkey",
))

# ---- Koalas & Kangaroos -----------------------------------------------------------

def koala_shape(cx, cy, size, colors, opacity=1):
    fill = colors[0]
    s = size / 100.0
    items = [
        circle(cx - 50 * s, cy - 35 * s, 26 * s, fill, opacity),
        circle(cx + 50 * s, cy - 35 * s, 26 * s, fill, opacity),
        circle(cx - 50 * s, cy - 35 * s, 14 * s, "#f4c6a5", opacity),
        circle(cx + 50 * s, cy - 35 * s, 14 * s, "#f4c6a5", opacity),
        circle(cx, cy + 5 * s, 55 * s, fill, opacity),
        circle(cx - 18 * s, cy - 5 * s, 6 * s, "#1a1a1a", opacity),
        circle(cx + 18 * s, cy - 5 * s, 6 * s, "#1a1a1a", opacity),
        ellipse(cx, cy + 18 * s, 12 * s, 10 * s, "#1a1a1a", opacity),
    ]
    return group(items)


def kangaroo_shape(cx, cy, size, colors, opacity=1):
    fill = colors[0]
    s = size / 100.0
    items = [
        ellipse(cx, cy + 10 * s, 45 * s, 60 * s, fill, opacity),
        circle(cx + 10 * s, cy - 60 * s, 30 * s, fill, opacity),
        polygon([(cx-5*s, cy-85*s), (cx+10*s, cy-85*s), (cx+2*s, cy-110*s)], fill, opacity),
        polygon([(cx+20*s, cy-85*s), (cx+35*s, cy-85*s), (cx+28*s, cy-110*s)], fill, opacity),
        circle(cx + 22 * s, cy - 62 * s, 4 * s, "#1a1a1a", opacity),
        f'<path d="M {cx-30*s:.1f} {cy+50*s:.1f} Q {cx-70*s:.1f} {cy+80*s:.1f} {cx-80*s:.1f} {cy+120*s:.1f}" '
        f'fill="none" stroke="{fill}" stroke-width="{16*s:.1f}" stroke-linecap="round" opacity="{opacity:.2f}"/>',
    ]
    return group(items)


KOALA_KANGAROO_KINDS = ["koala", "kangaroo"]


def koala_or_kangaroo(cx, cy, size, colors, kind, opacity=1):
    return koala_shape(cx, cy, size, colors, opacity) if kind == "koala" else kangaroo_shape(cx, cy, size, colors, opacity)


cat("koalas-kangaroos", "Koalas & Kangaroos", titled_variants(
    "koalas-kangaroos",
    moods=["Cuddly", "Bouncy", "Outback", "Sleepy", "Aussie", "Playful", "Sunny"],
    palette_options=[("Grey", ["#adb5bd"]), ("Reddish Brown", ["#c07a4a"]),
                      ("Soft Tan", ["#d4a373"]), ("Charcoal", ["#6c757d"])],
    sky_options=[("Eucalyptus Grove", ["#d8f3dc", "#b7e4c7"]), ("Outback Sunset", ["#ff9f7b", "#ffcf8a"]),
                 ("Australian Sky", ["#fff3e0", "#ffe4c2"])],
    factory=lambda colors, sky: multi_kind_scene(koala_or_kangaroo, KOALA_KANGAROO_KINDS, colors, sky, 5, (190, 280)),
    name="",
))

# ---- Glitter & Sparkle -----------------------------------------------------------

cat("glitter-sparkle", "Glitter & Sparkle", titled_variants(
    "glitter-sparkle",
    moods=["Dazzling", "Shimmering", "Glittery", "Glam", "Shiny", "Twinkling", "Metallic"],
    palette_options=[("Gold", ["#ffd700", "#fff3b0"]), ("Rose Gold", ["#ff9fd6", "#ffd6e8"]),
                      ("Silver", ["#e0e0e0", "#ffffff"]), ("Holographic", ["#9b5de5", "#00f5d4", "#f15bb5"])],
    sky_options=[("Sparkle", ["#2b2d42", "#3a0ca3"]), ("Glam", ["#fdf0ff", "#ffe6f7"]),
                 ("Disco", ["#0d0221", "#190535"])],
    factory=lambda colors, sky: scene(lambda cx, cy, s, r, o: sparkle_shape(cx, cy, s * 0.4, rng_choice_colors(r) if len(colors) < 2 else colors[int(abs(r)) % len(colors)], r, o), sky, 40, (30, 100), True),
    name="Glitter",
))


# ============================================================================
# REALISTIC STYLE PACK -- 150 more backgrounds (10 each) layering the
# "realistic style" treatment (bokeh backdrop, contact shadow, texture
# strokes, soft highlight, vignette -- see realistic_scene()) onto existing
# shape functions with muted, natural color palettes, across the 15
# categories where it reads best. These append into their categories'
# existing tabs rather than creating new ones.
# ============================================================================

MUTED_SKIES = [
    ("Soft Focus", ["#c9d6e0", "#eef3f6"]),
    ("Golden Hour", ["#e8c48c", "#f4dfb8"]),
    ("Overcast Light", ["#b8c4cc", "#dbe4ea"]),
]
PORTRAIT_MOODS = ["Golden Hour", "Soft Focus", "Studio Light", "Candid"]

# ---- Huskies (realistic) -----------------------------------------------------
HUSKY_REALISTIC_PALETTES = [
    ("Charcoal & Cream Husky", ["#5b5f66", "#f2efe9", "#5b9bd5", "#5b9bd5"]),
    ("Copper & Cream Husky", ["#9c5a34", "#f4e8d8", "#7a5230", "#7a5230"]),
    ("Snow White Husky", ["#f0efe9", "#ffffff", "#5b9bd5", "#7a5230"]),
    ("Silver Husky", ["#8b8f95", "#e6e3dd", "#5b9bd5", "#5b9bd5"]),
    ("Sable Husky", ["#a9895e", "#f0e6d2", "#7a5230", "#7a5230"]),
]
cat("huskies", "Huskies", titled_variants(
    "huskies-realistic", PORTRAIT_MOODS, HUSKY_REALISTIC_PALETTES, MUTED_SKIES,
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: husky_face_shape(cx, cy, s, colors[0], colors[1], colors[2], colors[3], o, "face"),
        sky, sky, 4, (260, 360), texture_color="#3a2a1a"),
    count=10, name="Portrait",
), style="realistic")

# ---- Cute Animals (realistic) -------------------------------------------------
CUTE_ANIMAL_REALISTIC = [
    ("Golden Puppy", ["#e8b84b", "#8a5a2b", "puppy"]),
    ("Tabby Kitten", ["#c9a066", "#c9a066", "kitten"]),
    ("Snow Bunny", ["#f7f7f7", "#ffd6e8", "bunny"]),
    ("Red Fox", ["#c1541c", "#ffffff", "fox"]),
    ("Giant Panda", ["#ffffff", "#2b2b2b", "panda"]),
]
cat("cute-animals", "Cute Animals", titled_variants(
    "cute-animals-realistic", PORTRAIT_MOODS, CUTE_ANIMAL_REALISTIC, MUTED_SKIES,
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: animal_face_shape(cx, cy, s, colors[0], colors[1], colors[2], o),
        sky, sky, 4, (250, 350), texture_color="#3a2a1a"),
    count=10, name="Close-Up",
), style="realistic")

# ---- Cats & Kittens (realistic) -----------------------------------------------
CAT_REALISTIC = [
    ("Tabby Cat", ["#c9a066"]), ("Black Cat", ["#2b2b2b"]), ("White Cat", ["#f7f7f7"]),
    ("Grey Cat", ["#8b8f95"]), ("Ginger Cat", ["#d97a3d"]),
]
cat("cats-kittens", "Cats & Kittens", titled_variants(
    "cats-realistic", PORTRAIT_MOODS, CAT_REALISTIC, MUTED_SKIES,
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: cat_face_shape(cx, cy, s, colors[0], o),
        sky, sky, 4, (250, 350), texture_color="#3a2a1a"),
    count=10, name="Portrait",
), style="realistic")

# ---- Farm & Barnyard (realistic) ----------------------------------------------
COW_REALISTIC = [
    ("Holstein Cow", ["#f4f1ea", "#1a1a1a"]), ("Jersey Cow", ["#a9895e", "#f0e6d2"]),
    ("Highland Cow", ["#9c5a34", "#c9895e"]), ("Angus Cow", ["#2b2b2b", "#3a3a3a"]),
    ("Hereford Cow", ["#9c3b22", "#f4f1ea"]),
]
cat("farm-barnyard", "Farm & Barnyard", titled_variants(
    "farm-realistic", PORTRAIT_MOODS, COW_REALISTIC, MUTED_SKIES,
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: cow_shape(cx, cy, s, colors[0], colors[1], o),
        sky, sky, 4, (220, 320), texture_color="#5b4636"),
    count=10, name="Pasture Portrait",
), style="realistic")

# ---- Arctic & Polar Animals (realistic) ---------------------------------------
def arctic_realistic_motif(cx, cy, s, colors, o):
    kind = colors[-1]
    if kind == "penguin":
        return penguin_shape(cx, cy, s, o)
    if kind == "polarbear":
        return polar_bear_shape(cx, cy, s, o)
    if kind == "walrus":
        return walrus_shape(cx, cy, s, o)
    return seal_shape(cx, cy, s, colors[0], o)


ARCTIC_REALISTIC = [
    ("Emperor Penguin", ["#adb5bd", "penguin"]), ("Polar Bear", ["#ffffff", "polarbear"]),
    ("Harbor Seal", ["#8d99ae", "seal"]), ("Walrus", ["#b98d6f", "walrus"]),
    ("Snow Seal", ["#c9d6e0", "seal"]),
]
cat("arctic-polar", "Arctic & Polar Animals", titled_variants(
    "arctic-realistic", PORTRAIT_MOODS, ARCTIC_REALISTIC, MUTED_SKIES,
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: arctic_realistic_motif(cx, cy, s, colors, o),
        sky, sky, 4, (220, 320)),
    count=10, name="in the Wild",
), style="realistic")

# ---- Ocean & Sea Life (realistic) ---------------------------------------------
def ocean_realistic_motif(cx, cy, s, colors, r, o):
    kind = colors[-1]
    if kind == "whale":
        return whale_shape(cx, cy, s, colors[0], o, r)
    if kind == "dolphin":
        return dolphin_shape(cx, cy, s, colors[0], o, r)
    if kind == "turtle":
        return sea_turtle_shape(cx, cy, s, colors[0], colors[0], o, r)
    return octopus_shape(cx, cy, s, colors[0], o)


OCEAN_REALISTIC = [
    ("Humpback Whale", ["#3d5a80", "whale"]), ("Bottlenose Dolphin", ["#5b7c99", "dolphin"]),
    ("Green Sea Turtle", ["#2d6a4f", "turtle"]), ("Reef Octopus", ["#6a4c93", "octopus"]),
    ("Orca", ["#1a1a1a", "whale"]),
]
cat("ocean-sea-life", "Ocean & Sea Life", titled_variants(
    "ocean-realistic", PORTRAIT_MOODS, OCEAN_REALISTIC, [
        ("Deep Blue", ["#03045e", "#0077b6"]), ("Sunlit Water", ["#48cae4", "#ade8f4"]),
        ("Twilight Sea", ["#023e8a", "#0096c7"]),
    ],
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: ocean_realistic_motif(cx, cy, s, colors, r, o),
        sky, sky, 3, (240, 340)),
    count=10, name="in the Deep",
), style="realistic")

# ---- Birds & Feathers (realistic) ----------------------------------------------
def birds_realistic_motif(cx, cy, s, colors, o):
    kind = colors[-1]
    if kind == "owl":
        return owl_shape(cx, cy, s, colors[0], colors[1], "#ffd166", o)
    if kind == "flamingo":
        return flamingo_shape(cx, cy, s, colors[0], o)
    return parrot_shape(cx, cy, s, colors[0], colors[1], o)


BIRDS_REALISTIC = [
    ("Barn Owl", ["#c9b18a", "#f0e6d2", "owl"]), ("Snowy Owl", ["#f0efe9", "#ffffff", "owl"]),
    ("Scarlet Macaw", ["#c1272d", "#f4a261", "parrot"]), ("Flamingo", ["#e8879b", "#e8879b", "flamingo"]),
    ("Great Horned Owl", ["#7a6a52", "#c9b18a", "owl"]),
]
cat("birds-feathers", "Birds & Feathers", titled_variants(
    "birds-realistic", PORTRAIT_MOODS, BIRDS_REALISTIC, MUTED_SKIES,
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: birds_realistic_motif(cx, cy, s, colors, o),
        sky, sky, 4, (220, 320), texture_color="#5b4636", texture_count=18),
    count=10, name="in Flight",
), style="realistic")

# ---- Safari & Desert (realistic) ------------------------------------------------
def safari_realistic_motif(cx, cy, s, colors, o):
    kind = colors[-1]
    if kind == "giraffe":
        return giraffe_shape(cx, cy, s, colors[0], colors[1], o)
    if kind == "zebra":
        return zebra_shape(cx, cy, s, o)
    if kind == "camel":
        return camel_shape(cx, cy, s, colors[0], o)
    return elephant_shape(cx, cy, s, colors[0], o)


SAFARI_REALISTIC = [
    ("African Elephant", ["#8d99ae", "elephant"]), ("Reticulated Giraffe", ["#c9895e", "#6b4423", "giraffe"]),
    ("Plains Zebra", ["#f4f1ea", "zebra"]), ("Dromedary Camel", ["#c9a066", "camel"]),
    ("Savanna Elephant", ["#a9a9a9", "elephant"]),
]
cat("safari-desert", "Safari & Desert", titled_variants(
    "safari-realistic", PORTRAIT_MOODS, SAFARI_REALISTIC, [
        ("Savanna Dust", ["#e8c48c", "#f4dfb8"]), ("Desert Haze", ["#f4a261", "#ffe8b0"]),
        ("Golden Plains", ["#e9c46a", "#fff3e0"]),
    ],
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: safari_realistic_motif(cx, cy, s, colors, o),
        sky, sky, 3, (240, 340), texture_color="#5b4636", texture_count=16),
    count=10, name="on Safari",
), style="realistic")

# ---- Nature Scenes (realistic) --------------------------------------------------
def realistic_nature_scene(kind, sky, fog_colors):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        blur_id = svg.blur_filter(24)
        for item in bokeh_backdrop(rng, fog_colors, blur_id, n=8, r_range=(200, 420), opacity_range=(0.15, 0.28)):
            svg.add(item)
        if kind == "mountains":
            for color, y, spread in [("#5c6b73", 0.6, 1.0), ("#7d8f96", 0.72, 0.85), ("#9fb1b8", 0.85, 0.7)]:
                pts = [(0, H)]
                x = 0
                while x < W:
                    pts.append((x, H * y - rng.uniform(0, 150) * spread))
                    x += rng.uniform(200, 300)
                pts.append((W, H))
                svg.add(polygon(pts, color, 0.92))
            svg.add(f'<circle cx="{W*0.78:.0f}" cy="{H*0.16:.0f}" r="90" fill="#fffaf0" opacity="0.85" filter="url(#{blur_id})"/>')
        else:  # forest
            for i, (color, y, s) in enumerate([("#3a5a45", 0.55, 1), ("#4d6e58", 0.68, 0.85), ("#5f8067", 0.82, 0.7)]):
                for _ in range(7):
                    x = rng.uniform(0, W)
                    svg.add(triangle_shape(x, H * y, 170 * s, color, 0.9))
                    svg.add(triangle_shape(x, H * y - 95 * s, 140 * s, color, 0.9))
        svg.add(vignette(svg, 0.22))
    return build


cat("nature-scenes", "Nature Scenes", [
    ("Misty Mountain Vista", realistic_nature_scene("mountains", ["#dbe4ea", "#b8c4cc"], ["#ffffff", "#c9d6e0"])),
    ("Golden Hour Mountains", realistic_nature_scene("mountains", ["#e8c48c", "#f4dfb8"], ["#fff3d6", "#ffdca8"])),
    ("Foggy Forest Morning", realistic_nature_scene("forest", ["#c9d6e0", "#dbe4ea"], ["#ffffff", "#e6ede8"])),
    ("Deep Woods Twilight", realistic_nature_scene("forest", ["#2b3a3a", "#3d5a50"], ["#4d6e58", "#1b2e2a"])),
    ("Alpine Sunrise", realistic_nature_scene("mountains", ["#f4a261", "#ffe8b0"], ["#ffd6a5", "#fff3d6"])),
    ("Rainforest Haze", realistic_nature_scene("forest", ["#95d5b2", "#d8f3dc"], ["#eafff1", "#c9e8d0"])),
    ("Overcast Peaks", realistic_nature_scene("mountains", ["#8d99ae", "#adb5bd"], ["#c9d6e0", "#e9ecef"])),
    ("Autumn Forest Light", realistic_nature_scene("forest", ["#e9c46a", "#f4a261"], ["#ffe8b0", "#ffcf8a"])),
    ("Snow-Capped Mountains", realistic_nature_scene("mountains", ["#eef3f6", "#c9d6e0"], ["#ffffff", "#dbe4ea"])),
    ("Evergreen Forest Mist", realistic_nature_scene("forest", ["#4d6e58", "#95d5b2"], ["#d8f3dc", "#c9d6e0"])),
], style="realistic")

# ---- Space & Planets (realistic) ------------------------------------------------
def realistic_space_scene(kind, sky, nebula_colors):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        for _ in range(180):
            r = rng.uniform(1.5, 4.5)
            svg.add(circle(rng.uniform(0, W), rng.uniform(0, H), r, "#ffffff", rng.uniform(0.3, 0.95)))
        blur_id = svg.blur_filter(30)
        for item in bokeh_backdrop(rng, nebula_colors, blur_id, n=6, r_range=(220, 460), opacity_range=(0.16, 0.3)):
            svg.add(item)
        cx, cy = W * rng.uniform(0.35, 0.65), H * rng.uniform(0.3, 0.55)
        if kind == "moon":
            svg.add(shadow_ellipse(cx, cy + 260, 220, 60, blur_id, 0.2))
            svg.add(moon_shape(cx, cy, 260, "#e6e3dd", 0.97))
            svg.add(glow_highlight(svg, cx - 60, cy - 70, 220, 0.3))
        else:  # planet
            svg.add(planet_shape(cx, cy, 220, rng.choice(nebula_colors), "#ffffff", 0.95))
            svg.add(glow_highlight(svg, cx - 60, cy - 70, 200, 0.28))
        svg.add(vignette(svg, 0.28))
    return build


cat("space-planets", "Space & Planets", [
    ("Lunar Surface Close-Up", realistic_space_scene("moon", ["#03071e", "#0a2540"], ["#3a0ca3", "#7209b7"])),
    ("Deep Space Nebula", realistic_space_scene("planet", ["#0d0221", "#190535"], ["#f72585", "#7209b7", "#3a0ca3"])),
    ("Saturn-Like Ringed World", realistic_space_scene("planet", ["#020024", "#090979"], ["#4361ee", "#4cc9f0"])),
    ("Blood Moon Rising", realistic_space_scene("moon", ["#1a0000", "#3a0ca3"], ["#e63946", "#7209b7"])),
    ("Crater-Marked Moon", realistic_space_scene("moon", ["#0f0c29", "#302b63"], ["#8b8f95", "#c9d6e0"])),
    ("Distant Gas Giant", realistic_space_scene("planet", ["#03045e", "#023e8a"], ["#00f5d4", "#0077b6"])),
    ("Starfield Observation", realistic_space_scene("moon", ["#000814", "#001d3d"], ["#4cc9f0", "#a6e3ff"])),
    ("Amber Nebula Cloud", realistic_space_scene("planet", ["#1a1a40", "#0d1b4c"], ["#f4a261", "#e76f51"])),
    ("Twin Moons Night", realistic_space_scene("moon", ["#10002b", "#240046"], ["#c8b6ff", "#9b5de5"])),
    ("Emerald Nebula Field", realistic_space_scene("planet", ["#03071e", "#03045e"], ["#06d6a0", "#2ec4b6"])),
], style="realistic")

# ---- Dinosaurs & Prehistoric (realistic) -----------------------------------------
DINO_REALISTIC = [
    ("Olive Green Dino", ["#5f6b3a", "#3d4526"]), ("Slate Grey Dino", ["#6c757d", "#495057"]),
    ("Earthy Brown Dino", ["#7a5c3e", "#5b4636"]), ("Moss Green Dino", ["#4a6b3a", "#2d3f22"]),
    ("Sandstone Dino", ["#a68a64", "#7a5c3e"]),
]
cat("dinosaurs-prehistoric", "Dinosaurs & Prehistoric", titled_variants(
    "dino-realistic", PORTRAIT_MOODS, DINO_REALISTIC, [
        ("Prehistoric Jungle", ["#3a5a45", "#4d6e58"]), ("Volcanic Haze", ["#f4a261", "#e76f51"]),
        ("Fossil Dig Site", ["#e8c48c", "#f4dfb8"]),
    ],
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: dino_shape(cx, cy, s, colors[0], colors[1], o),
        sky, sky, 3, (240, 340), texture_color="#2b2b2b", texture_count=14),
    count=10, name="",
), style="realistic")

# ---- Reptiles & Amphibians (realistic) --------------------------------------------
def reptile_realistic_motif(cx, cy, s, colors, r, o):
    kind = colors[-1]
    if kind == "turtle":
        return turtle_shape(cx, cy, s, colors[0], colors[0], o)
    if kind == "chameleon":
        return chameleon_shape(cx, cy, s, colors[0], o)
    if kind == "snake":
        return snake_shape(cx, cy, s, colors[0], o, r)
    return frog_shape(cx, cy, s, colors[0], o)


REPTILE_REALISTIC = [
    ("Red-Eyed Tree Frog", ["#4a8f3c", "frog"]), ("Box Turtle", ["#5b4636", "turtle"]),
    ("Veiled Chameleon", ["#4a8f6b", "chameleon"]), ("Corn Snake", ["#a9895e", "snake"]),
    ("Poison Dart Frog", ["#f4d35e", "frog"]),
]
cat("reptiles-amphibians", "Reptiles & Amphibians", titled_variants(
    "reptile-realistic", PORTRAIT_MOODS, REPTILE_REALISTIC, [
        ("Rainforest Floor", ["#2b3a2a", "#3d5a45"]), ("Terrarium Light", ["#95d5b2", "#d8f3dc"]),
        ("Wetland Morning", ["#c9d6e0", "#eef3f6"]),
    ],
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: reptile_realistic_motif(cx, cy, s, colors, r, o),
        sky, sky, 4, (200, 300)),
    count=10, name="Close-Up",
), style="realistic")

# ---- Winter & Holiday (realistic) --------------------------------------------------
def realistic_winter_scene(sky, snow_colors):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        blur_id = svg.blur_filter(20)
        for item in bokeh_backdrop(rng, snow_colors, blur_id, n=7, r_range=(160, 340), opacity_range=(0.14, 0.26)):
            svg.add(item)
        for _ in range(4):
            cx, cy = rng.uniform(200, W - 200), rng.uniform(H * 0.5, H * 0.85)
            size = rng.uniform(220, 320)
            svg.add(shadow_ellipse(cx, cy + size * 0.85, size * 0.5, size * 0.14, blur_id, 0.22))
            svg.add(snowman_shape(cx, cy, size, 0.97))
        for _ in range(40):
            svg.add(circle(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(2, 5), "#ffffff", rng.uniform(0.5, 0.9)))
        svg.add(vignette(svg, 0.2))
    return build


cat("winter-holiday", "Winter & Holiday", [
    ("Snowfall at Dusk", realistic_winter_scene(["#4a5a6b", "#2b3a4a"], ["#c9d6e0", "#8b8f95"])),
    ("Frosty Morning Light", realistic_winter_scene(["#dbe4ea", "#eef3f6"], ["#ffffff", "#c9d6e0"])),
    ("Blue Hour Snowfall", realistic_winter_scene(["#023e8a", "#0096c7"], ["#4cc9f0", "#a6e3ff"])),
    ("Golden Winter Sunset", realistic_winter_scene(["#e8c48c", "#f4dfb8"], ["#ffd6a5", "#fff3d6"])),
    ("Overcast Snow Day", realistic_winter_scene(["#8d99ae", "#adb5bd"], ["#c9d6e0", "#e9ecef"])),
    ("Moonlit Snowfield", realistic_winter_scene(["#0d1b4c", "#1a1a40"], ["#8b8f95", "#c9d6e0"])),
    ("Cabin Window Snow", realistic_winter_scene(["#5b4636", "#3a2a1a"], ["#ffe8b0", "#f4dfb8"])),
    ("Pink Winter Dawn", realistic_winter_scene(["#ffb3c6", "#ffe0eb"], ["#ffffff", "#ffd6e8"])),
    ("Deep Winter Night", realistic_winter_scene(["#03071e", "#0a2540"], ["#4cc9f0", "#8b8f95"])),
    ("Soft Grey Snowscape", realistic_winter_scene(["#c9d6e0", "#dbe4ea"], ["#ffffff", "#eef3f6"])),
], style="realistic")

# ---- Summer & Beach (realistic) --------------------------------------------------
def realistic_beach_scene(sky, haze_colors):
    def build(svg, rng):
        grad_bg(svg, sky, 100)
        blur_id = svg.blur_filter(22)
        for item in bokeh_backdrop(rng, haze_colors, blur_id, n=7, r_range=(180, 380), opacity_range=(0.14, 0.26)):
            svg.add(item)
        svg.add(f'<circle cx="{W*0.5:.0f}" cy="{H*0.22:.0f}" r="140" fill="#fff3d6" opacity="0.9" filter="url(#{blur_id})"/>')
        svg.add(circle(W * 0.5, H * 0.22, 90, "#ffe8b0", 0.95))
        svg.add(rect(0, H * 0.62, W, H * 0.1, "#4a8fa8", opacity=0.85))
        svg.add(rect(0, H * 0.72, W, H * 0.28, "#e8c48c", opacity=0.9))
        for _ in range(3):
            cx, cy = rng.uniform(150, W - 150), H * rng.uniform(0.55, 0.68)
            svg.add(shadow_ellipse(cx, cy + 210, 90, 22, blur_id, 0.2))
            svg.add(palm_tree_shape(cx, cy, 220, "#5b4636", "#3d5a45", 0.95))
        svg.add(vignette(svg, 0.2))
    return build


cat("summer-beach", "Summer & Beach", [
    ("Golden Hour Shoreline", realistic_beach_scene(["#ffe8b0", "#ffcf8a"], ["#fff3d6", "#ffd6a5"])),
    ("Turquoise Lagoon", realistic_beach_scene(["#a8e6ff", "#dff7ff"], ["#48cae4", "#ade8f4"])),
    ("Sunset Beach Haze", realistic_beach_scene(["#ff9f7b", "#ff6f91"], ["#ffcf8a", "#ff9f7b"])),
    ("Misty Morning Coast", realistic_beach_scene(["#c9d6e0", "#eef3f6"], ["#ffffff", "#dbe4ea"])),
    ("Tropical Noon Light", realistic_beach_scene(["#4a8fa8", "#7fc8d8"], ["#a8e6ff", "#dff7ff"])),
    ("Pastel Beach Dawn", realistic_beach_scene(["#ffd6e8", "#fff0f5"], ["#ffe0eb", "#ffffff"])),
    ("Overcast Shoreline", realistic_beach_scene(["#8d99ae", "#adb5bd"], ["#c9d6e0", "#e9ecef"])),
    ("Golden Sand Dunes", realistic_beach_scene(["#e9c46a", "#fff3e0"], ["#ffe8b0", "#fff3d6"])),
    ("Twilight Palm Silhouette", realistic_beach_scene(["#3a0ca3", "#7209b7"], ["#c8b6ff", "#9b5de5"])),
    ("Clear Blue Coastline", realistic_beach_scene(["#00b4d8", "#90e0ef"], ["#a8e6ff", "#caf0f8"])),
], style="realistic")

# ---- Dogs & Puppies (realistic) --------------------------------------------------
DOG_REALISTIC = [
    ("Golden Retriever", ["#e8b84b", "#f4d78a", "labrador"]), ("Chocolate Lab", ["#6b4423", "#8a5a2b", "labrador"]),
    ("Corgi", ["#e8b84b", "#f4f1ea", "corgi"]), ("Fawn Pug", ["#d4a373", "#5b4636", "pug"]),
    ("Tricolor Beagle", ["#8a5a2b", "#f4f1ea", "beagle"]),
]
cat("dogs-puppies", "Dogs & Puppies", titled_variants(
    "dogs-realistic", PORTRAIT_MOODS, DOG_REALISTIC, MUTED_SKIES,
    factory=lambda colors, sky: realistic_scene(
        lambda cx, cy, s, r, o: dog_breed_shape(cx, cy, s, colors[:2], colors[2], o),
        sky, sky, 4, (250, 350), texture_color="#3a2a1a"),
    count=10, name="Portrait",
), style="realistic")


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


# Extra search-recall tags per category, layered on top of the category name,
# style, and title keywords for every background in that category. This is
# what makes e.g. searching "dog" or "pet" surface Huskies, or "sea" surface
# Ocean & Sea Life, without relying on the title alone.
CATEGORY_TAGS = {
    "rainbow-gradients": ["rainbow", "gradient", "colorful", "sky", "pastel"],
    "geometric-patterns": ["pattern", "shapes", "geometric", "polka dot", "stripes"],
    "cute-animals": ["animal", "animals", "pet", "cute", "baby animal"],
    "nature-scenes": ["nature", "outdoors", "scenery", "landscape"],
    "space-planets": ["space", "galaxy", "stars", "astronomy", "cosmic"],
    "flowers-florals": ["flower", "floral", "garden", "bloom", "botanical"],
    "butterflies-insects": ["butterfly", "insect", "bug", "garden", "wings"],
    "mermaids-underwater": ["mermaid", "underwater", "ocean", "sea", "fantasy"],
    "fairies-magic": ["fairy", "magic", "fantasy", "sparkle", "enchanted"],
    "princesses-castles": ["princess", "castle", "royal", "fairytale", "crown"],
    "hearts-romance": ["heart", "love", "romance", "valentine"],
    "fashion-shopping": ["fashion", "style", "clothes", "shopping", "boutique"],
    "unicorns-fantasy": ["unicorn", "fantasy", "magical", "rainbow", "mythical"],
    "cats-kittens": ["cat", "kitten", "pet", "feline"],
    "bows-ribbons": ["bow", "ribbon", "cute", "decorative", "lace"],
    "sports-games": ["sports", "game", "athletic", "play", "ball"],
    "dinosaurs-prehistoric": ["dinosaur", "prehistoric", "dino", "jurassic", "fossil"],
    "vehicles": ["vehicle", "car", "truck", "transportation", "travel"],
    "superheroes-action": ["superhero", "hero", "action", "comic", "cape"],
    "food-treats": ["food", "treat", "snack", "sweet", "dessert"],
    "music-dance": ["music", "dance", "song", "rhythm", "instrument"],
    "winter-holiday": ["winter", "holiday", "christmas", "snow", "festive"],
    "summer-beach": ["summer", "beach", "sun", "vacation", "tropical"],
    "weather": ["weather", "sky", "clouds", "rain", "climate"],
    "neon-bold": ["neon", "bright", "glow", "bold", "vibrant"],
    "huskies": ["dog", "dogs", "puppy", "husky", "pet", "sled dog", "winter dog"],
    "arctic-polar": ["arctic", "polar", "cold", "snow", "ice", "winter animal"],
    "farm-barnyard": ["farm", "barnyard", "farm animal", "countryside", "rural"],
    "ocean-sea-life": ["ocean", "sea", "marine", "underwater", "aquatic", "fish"],
    "birds-feathers": ["bird", "feather", "wings", "tropical bird", "flying"],
    "robots-gadgets": ["robot", "gadget", "tech", "mechanical", "futuristic"],
    "pirates-treasure": ["pirate", "treasure", "ship", "ocean", "adventure"],
    "camping-outdoors": ["camping", "outdoors", "tent", "adventure", "wilderness"],
    "circus-carnival": ["circus", "carnival", "fair", "fun", "festival"],
    "construction-diggers": ["construction", "truck", "digger", "builder", "machine"],
    "school-learning": ["school", "learning", "education", "study", "classroom"],
    "safari-desert": ["safari", "desert", "wild animal", "savanna", "jungle animal"],
    "reptiles-amphibians": ["reptile", "amphibian", "frog", "turtle", "lizard"],
    "emoji-faces": ["emoji", "smiley", "face", "happy", "mood"],
    "board-games-puzzles": ["board game", "puzzle", "game night", "dice", "cards"],
    "dogs-puppies": ["dog", "dogs", "puppy", "puppies", "pet", "breed"],
    "horses-ponies": ["horse", "pony", "ponies", "equestrian", "stable", "riding"],
    "ballet-dance": ["ballet", "dance", "dancer", "ballerina", "tutu"],
    "autumn-fall": ["autumn", "fall", "leaves", "pumpkin", "harvest", "cozy"],
    "spring-garden": ["spring", "garden", "gardening", "flowers", "bloom", "bees"],
    "dragons-mythical": ["dragon", "mythical", "fantasy", "legend", "magic"],
    "wizards-magic": ["wizard", "magic", "spell", "witch", "potion"],
    "treehouses-forts": ["treehouse", "fort", "hideout", "forest", "adventure"],
    "roller-skating": ["roller skate", "skating", "scooter", "wheels", "fun"],
    "baking-kitchen": ["baking", "kitchen", "cookies", "cupcake", "chef", "cooking"],
    "hiking-nature-trails": ["hiking", "trail", "nature", "mountain", "adventure", "outdoors"],
    "tea-party": ["tea party", "teacup", "teapot", "cookies", "fancy", "whimsical"],
    "race-cars-speed": ["race car", "racing", "speed", "fast", "checkered flag"],
    "jungle-rainforest": ["jungle", "rainforest", "tropical", "monkey", "vine", "exotic"],
    "koalas-kangaroos": ["koala", "kangaroo", "australia", "australian animal", "marsupial"],
    "glitter-sparkle": ["glitter", "sparkle", "shiny", "glam", "shimmer"],
}

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "for", "to", "and", "with",
    "your", "my", "is", "day", "time",
}


def title_keywords(title):
    """Meaningful, deduped keywords pulled from a background's title, for
    search recall beyond the category name (e.g. "Aurora Husky Night" ->
    aurora, husky, night)."""
    words = re.findall(r"[a-z']+", title.lower())
    seen, out = set(), []
    for w in words:
        if len(w) <= 2 or w in _STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    entries = []
    total = 0
    style_counts = {}
    for cat_def in CATS:
        slug = cat_def["slug"]
        cat_dir = os.path.join(OUT_DIR, slug)
        os.makedirs(cat_dir, exist_ok=True)
        bonus = CATEGORY_TAGS.get(slug, [])
        seen_slugs = {}
        for i, (title, builder, style) in enumerate(cat_def["variants"], start=1):
            rng = random.Random(f"{slug}-{i}-{title}")
            svg = Svg()
            builder(svg, rng)
            file_slug = slugify(title)
            # titled_variants() only guarantees unique *titles*; slugify()
            # drops case and punctuation, so two distinct titles can still
            # collide here ("Game On!" / "Game On") and silently overwrite
            # each other's artwork, leaving a duplicate id in the manifest.
            if file_slug in seen_slugs:
                raise ValueError(
                    f"{slug}: titles {seen_slugs[file_slug]!r} and {title!r} both "
                    f"slugify to {file_slug!r} -- rename one of them"
                )
            seen_slugs[file_slug] = title
            filename = f"{file_slug}.svg"
            filepath = os.path.join(cat_dir, filename)
            with open(filepath, "w") as f:
                f.write(svg.render())

            tags = []
            for t in ([slug.replace("-", " "), cat_def["name"].lower(), style]
                      + bonus + title_keywords(title)):
                if t not in tags:
                    tags.append(t)

            credit = ("Original artwork generated for this app "
                      "(enhanced realistic-style illustration)" if style == "realistic"
                      else "Original artwork generated for this app")

            entries.append({
                "id": f"{slug}/{file_slug}",
                "title": title,
                "category": slug,
                "categoryName": cat_def["name"],
                "filename": f"images/backgrounds/{slug}/{filename}",
                "style": style,
                "credit": credit,
                "tags": tags,
            })
            style_counts[style] = style_counts.get(style, 0) + 1
            total += 1

    # Merge in real photographs, if scripts/import_real_photos.py has been run.
    # Those files aren't generated by this script and are left untouched here
    # -- only their metadata (already includes CC attribution) gets merged.
    real_photos_path = os.path.join(ROOT, "scripts", "real_photos_manifest.json")
    if os.path.exists(real_photos_path):
        with open(real_photos_path) as f:
            real_photos = json.load(f)
        for entry in real_photos:
            if not os.path.exists(os.path.join(ROOT, entry["filename"])):
                print(f"WARNING: {entry['filename']} listed in real_photos_manifest.json but "
                      f"missing on disk -- run scripts/import_real_photos.py. Skipping.")
                continue
            entries.append(entry)
            style_counts[entry["style"]] = style_counts.get(entry["style"], 0) + 1
            total += 1

    with open(JSON_PATH, "w") as f:
        json.dump({
            "categories": [{"slug": c["slug"], "name": c["name"]} for c in CATS],
            "backgrounds": entries,
        }, f, indent=2)
    print(f"Generated {total} backgrounds across {len(CATS)} categories. Styles: {style_counts}")


if __name__ == "__main__":
    main()
