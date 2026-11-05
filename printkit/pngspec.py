"""Check a PNG print file against a print-on-demand file specification you supply.

Checks only technical properties (dimensions, colour mode, DPI metadata, transparent
corners, amount of visible content). It does not judge design quality. The spec is always
given by the caller; nothing here is tied to any particular shop or production system.
"""
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class Spec:
    width: int
    height: int
    dpi: int = 300
    require_alpha: bool = True
    transparent_corners: bool = True
    min_visible_fraction: float = 0.02


def check(path, spec):
    """Return a list of problems (empty = the file meets the spec)."""
    problems = []
    with open(path, "rb") as fh:
        head = fh.read(8)
    if head != b"\x89PNG\r\n\x1a\n":
        return ["not a PNG file"]
    im = Image.open(path)
    im.load()
    if im.size != (spec.width, spec.height):
        problems.append(f"size is {im.size[0]}x{im.size[1]}, expected {spec.width}x{spec.height}")
    dpi = im.info.get("dpi")
    if spec.dpi and (not dpi or round(dpi[0]) != spec.dpi or round(dpi[1]) != spec.dpi):
        problems.append(f"DPI metadata is {dpi}, expected {spec.dpi}")
    if spec.require_alpha and im.mode != "RGBA":
        problems.append(f"colour mode is {im.mode}, expected RGBA")
    if im.mode == "RGBA":
        a = np.asarray(im.getchannel("A"))
        if spec.transparent_corners and max(a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]) != 0:
            problems.append("corners are not transparent")
        visible = float((a > 0).mean())
        if visible < spec.min_visible_fraction:
            problems.append(f"only {visible:.1%} of the image is visible (minimum {spec.min_visible_fraction:.0%})")
    return problems
