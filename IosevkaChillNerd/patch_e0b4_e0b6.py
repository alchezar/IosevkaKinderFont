#!/usr/bin/env python3
"""Replace powerline half-circle glyphs U+E0B4 and U+E0B6 with rounded
half-squares (corner radius r=300 in font units, UPEM=1000)."""

import glob
import math
import sys
from array import array

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
from fontTools.ttLib.tables.ttProgram import Program


TOP = 971
BOTTOM = -291
ADVANCE = 500
OVERFLOW = 30  # flat edge overflow past the cell boundary (matches original)
R = 300        # corner radius

# Quadratic bezier quarter-circle approximation with 2 sub-arcs per corner.
# Off-curve sits on the tangent line extended R*tan(22.5 deg) from the arc endpoint.
# On-curve midpoint sits R/sqrt(2) from the corner center along the diagonal.
K_OFF = round(R * math.tan(math.radians(22.5)))  # tangent offset
K_MID = round(R / math.sqrt(2))                   # diagonal offset


def build_e0b4() -> Glyph:
    """Right-half: flat left edge at x=-OVERFLOW, rounded right corners."""
    left = -OVERFLOW        # -30
    right = ADVANCE         # 500
    cx_top = right - R      # 350
    cy_top = TOP - R        # 821
    cx_bot = right - R      # 350
    cy_bot = BOTTOM + R     # -141

    pts = [
        (left,                     TOP,              1),  # 0 top-left
        (left,                     BOTTOM,           1),  # 1 bottom-left
        (cx_bot,                   BOTTOM,           1),  # 2 start bot-right arc
        (cx_bot + K_OFF,           BOTTOM,           0),  # 3 off-curve (on bot tangent)
        (cx_bot + K_MID,           cy_bot - K_MID,   1),  # 4 mid-arc (45 deg)
        (right,                    cy_bot - K_OFF,   0),  # 5 off-curve (on right tangent)
        (right,                    cy_bot,           1),  # 6 end bot-right arc
        (right,                    cy_top,           1),  # 7 start top-right arc
        (right,                    cy_top + K_OFF,   0),  # 8 off-curve (on right tangent)
        (cx_top + K_MID,           cy_top + K_MID,   1),  # 9 mid-arc (45 deg)
        (cx_top + K_OFF,           TOP,              0),  # 10 off-curve (on top tangent)
        (cx_top,                   TOP,              1),  # 11 end top-right arc
    ]
    return _make_simple_glyph(pts)


def build_e0b6() -> Glyph:
    """Left-half: flat right edge at x=ADVANCE+OVERFLOW, rounded left corners."""
    left = 0                        # 0
    right = ADVANCE + OVERFLOW      # 530
    cx_top = left + R               # 150
    cy_top = TOP - R                # 821
    cx_bot = left + R               # 150
    cy_bot = BOTTOM + R             # -141

    pts = [
        (right,                    TOP,              1),  # 0 top-right
        (right,                    BOTTOM,           1),  # 1 bottom-right
        (cx_bot,                   BOTTOM,           1),  # 2 start bot-left arc
        (cx_bot - K_OFF,           BOTTOM,           0),  # 3 off-curve
        (cx_bot - K_MID,           cy_bot - K_MID,   1),  # 4 mid-arc
        (left,                     cy_bot - K_OFF,   0),  # 5 off-curve
        (left,                     cy_bot,           1),  # 6 end bot-left arc
        (left,                     cy_top,           1),  # 7 start top-left arc
        (left,                     cy_top + K_OFF,   0),  # 8 off-curve
        (cx_top - K_MID,           cy_top + K_MID,   1),  # 9 mid-arc
        (cx_top - K_OFF,           TOP,              0),  # 10 off-curve
        (cx_top,                   TOP,              1),  # 11 end top-left arc
    ]
    return _make_simple_glyph(pts)


def _make_simple_glyph(pts) -> Glyph:
    g = Glyph()
    g.numberOfContours = 1
    g.coordinates = GlyphCoordinates([(x, y) for x, y, _ in pts])
    g.flags = array("B", [on for _, _, on in pts])
    g.endPtsOfContours = [len(pts) - 1]
    g.program = Program()
    g.program.fromBytecode(b"")
    return g


PATCH_TAG = "patched-e0b4e0b6"


def bump_version(font: TTFont) -> None:
    head = font["head"]
    head.fontRevision = round(head.fontRevision + 0.001, 3)
    new_ver = head.fontRevision

    name_table = font["name"]
    version_str = f"Version {new_ver:.3f};{PATCH_TAG}"

    for rec in list(name_table.names):
        if rec.nameID == 5:
            rec.string = version_str.encode(
                "utf-16-be" if rec.platformID == 0 or rec.platformID == 3 else "mac-roman"
            )
        elif rec.nameID == 3:
            unique = f"{version_str};{rec.toUnicode()}"
            rec.string = unique.encode(
                "utf-16-be" if rec.platformID == 0 or rec.platformID == 3 else "mac-roman"
            )

    print(f"  bumped fontRevision -> {new_ver:.3f}")


def patch(path: str) -> None:
    font = TTFont(path)
    cmap = font.getBestCmap()
    glyf = font["glyf"]
    hmtx = font["hmtx"]

    replacements = {
        0xE0B4: build_e0b4(),
        0xE0B6: build_e0b6(),
    }
    for cp, new_glyph in replacements.items():
        name = cmap.get(cp)
        if name is None:
            print(f"  U+{cp:04X}: missing, skipping")
            continue
        old_adv = hmtx[name][0]
        glyf[name] = new_glyph
        new_glyph.recalcBounds(glyf)
        hmtx[name] = (old_adv, new_glyph.xMin)
        print(
            f"  U+{cp:04X} ({name}): "
            f"bbox=({new_glyph.xMin},{new_glyph.yMin},{new_glyph.xMax},{new_glyph.yMax}) "
            f"adv={old_adv} lsb={new_glyph.xMin}"
        )

    bump_version(font)
    font.save(path)
    font.close()


def main() -> None:
    files = sorted(glob.glob("IosevkaChillNerd-*.ttf"))
    print(f"Processing {len(files)} files...")
    for f in files:
        print(f"--- {f}")
        patch(f)
    print("Done.")


if __name__ == "__main__":
    main()
