"""Draw the non-character portrait frames (narration, the PDA and event opponents).

The dialogue/duel UI asks the portrait subsystem for every speaker and
opponent, including the narrator, the PDA and the event-only non-human
duelists (Pharaoh, the Goblin King mask and the Jinzo spirit).  These get
simple UI icons on the same #263541 panel as the cast portraits, so they no
longer fall back to an empty frame or a bare initial.

    python Tools/make_ui_portraits.py
"""

import os
import shutil

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "DuelAcademyIsland", "Content", "Data", "Portraits")

SIZE = 512
SS = 2                       # supersample, then downsample for clean edges
PANEL = (38, 53, 65)
GOLD = (226, 196, 110)
GOLD_DARK = (150, 118, 52)
CREAM = (240, 232, 208)
INK = (35, 30, 24)
CYAN = (108, 214, 232)
CYAN_DARK = (40, 112, 132)
NAVY = (24, 38, 52)
WHITE = (238, 244, 248)


def _rgb(color):
    return tuple(int(round(c * 255)) for c in color)


def _canvas():
    return Image.new("RGB", (SIZE * SS, SIZE * SS), PANEL)


def _save(image, name):
    image.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(OUT, name + ".png"), optimize=True)
    image.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(OUT, name + "_face.png"), optimize=True)


def narrator():
    im = _canvas()
    d = ImageDraw.Draw(im)
    u = SIZE * SS
    # parchment scroll
    left, top, right, bottom = 0.22 * u, 0.24 * u, 0.78 * u, 0.72 * u
    d.rounded_rectangle([left, top, right, bottom], radius=0.035 * u, fill=CREAM, outline=GOLD, width=6)
    d.rounded_rectangle([left - 0.035 * u, top - 0.03 * u, right + 0.035 * u, top + 0.035 * u],
                        radius=0.02 * u, fill=(222, 208, 176), outline=GOLD_DARK, width=4)
    d.rounded_rectangle([left - 0.035 * u, bottom - 0.035 * u, right + 0.035 * u, bottom + 0.03 * u],
                        radius=0.02 * u, fill=(222, 208, 176), outline=GOLD_DARK, width=4)
    # ruled lines
    for i in range(5):
        y = top + 0.09 * u + i * 0.07 * u
        d.line([left + 0.06 * u, y, right - 0.06 * u, y], fill=(180, 162, 124), width=3)
    # quill: shaft + feather vanes
    shaft = [(0.60 * u, 0.70 * u), (0.77 * u, 0.30 * u)]
    d.line(shaft, fill=GOLD_DARK, width=8)
    for i in range(7):
        t = 0.15 + i * 0.11
        x = 0.60 * u + (0.77 - 0.60) * u * t
        y = 0.70 * u - (0.70 - 0.30) * u * t
        w = (0.10 - i * 0.011) * u
        d.polygon([(x, y), (x - w * 0.55, y - w * 0.35), (x - w * 0.1, y - w * 0.85)],
                  fill=GOLD if i % 2 else (238, 214, 150))
    # ink well
    d.ellipse([0.68 * u, 0.67 * u, 0.83 * u, 0.80 * u], fill=NAVY, outline=GOLD, width=5)
    d.rectangle([0.70 * u, 0.66 * u, 0.81 * u, 0.70 * u], fill=GOLD_DARK)
    _save(im, "narrator")


def pda():
    im = _canvas()
    d = ImageDraw.Draw(im)
    u = SIZE * SS
    # body
    body = [0.29 * u, 0.17 * u, 0.71 * u, 0.84 * u]
    d.rounded_rectangle(body, radius=0.055 * u, fill=NAVY, outline=GOLD, width=7)
    # screen
    screen = [0.34 * u, 0.23 * u, 0.66 * u, 0.61 * u]
    d.rounded_rectangle(screen, radius=0.022 * u, fill=(18, 76, 92), outline=CYAN_DARK, width=4)
    d.rounded_rectangle([0.37 * u, 0.26 * u, 0.63 * u, 0.58 * u], radius=0.012 * u, fill=CYAN)
    # little map/card glyph on the screen
    d.line([0.40 * u, 0.50 * u, 0.46 * u, 0.40 * u, 0.52 * u, 0.48 * u, 0.60 * u, 0.33 * u],
           fill=NAVY, width=5)
    d.ellipse([0.555 * u, 0.30 * u, 0.585 * u, 0.33 * u], fill=(230, 92, 70))
    # buttons
    for i, x in enumerate((0.38, 0.48, 0.58)):
        d.ellipse([x * u, 0.68 * u, (x + 0.045) * u, 0.725 * u],
                  fill=CYAN if i == 1 else CYAN_DARK)
    d.rounded_rectangle([0.40 * u, 0.77 * u, 0.60 * u, 0.80 * u], radius=0.012 * u, fill=GOLD_DARK)
    # antenna
    d.line([0.65 * u, 0.17 * u, 0.71 * u, 0.09 * u], fill=GOLD, width=6)
    d.ellipse([0.695 * u, 0.065 * u, 0.73 * u, 0.10 * u], fill=GOLD)
    _save(im, "ui_pda")


def pharaoh():
    """Pharaoh the cat: the one non-human portrait the duel HUD asks for."""
    im = _canvas()
    d = ImageDraw.Draw(im)
    u = SIZE * SS
    fur = _rgb((0.58, 0.40, 0.25))
    fur_dark = _rgb((0.34, 0.22, 0.14))
    # ears
    for x0, x1 in ((0.27, 0.43), (0.57, 0.73)):
        d.polygon([(x0 * u, 0.38 * u), ((x0 + 0.05) * u, 0.15 * u), (x1 * u, 0.30 * u)],
                  fill=fur, outline=fur_dark, width=5)
        d.polygon([((x0 + 0.04) * u, 0.34 * u), ((x0 + 0.06) * u, 0.21 * u), ((x1 - 0.03) * u, 0.30 * u)],
                  fill=_rgb((0.86, 0.58, 0.58)))
    # head
    d.ellipse([0.28 * u, 0.29 * u, 0.72 * u, 0.76 * u], fill=fur, outline=fur_dark, width=7)
    # muzzle
    d.ellipse([0.38 * u, 0.50 * u, 0.62 * u, 0.71 * u], fill=_rgb((0.86, 0.72, 0.58)))
    # eyes
    for x in (0.39, 0.61):
        d.ellipse([(x - 0.055) * u, 0.41 * u, (x + 0.055) * u, 0.50 * u], fill=_rgb((0.98, 0.86, 0.36)),
                  outline=fur_dark, width=4)
        d.ellipse([(x - 0.018) * u, 0.435 * u, (x + 0.018) * u, 0.49 * u], fill=_rgb((0.08, 0.06, 0.05)))
        d.ellipse([(x - 0.008) * u, 0.445 * u, (x + 0.006) * u, 0.465 * u], fill=WHITE)
    # nose + mouth
    d.polygon([(0.485 * u, 0.545 * u), (0.515 * u, 0.545 * u), (0.50 * u, 0.57 * u)], fill=_rgb((0.84, 0.42, 0.48)))
    d.arc([0.455 * u, 0.55 * u, 0.505 * u, 0.60 * u], 20, 160, fill=fur_dark, width=4)
    d.arc([0.495 * u, 0.55 * u, 0.545 * u, 0.60 * u], 20, 160, fill=fur_dark, width=4)
    # whiskers
    for side in (-1, 1):
        for dz in (-0.02, 0.02):
            d.line([(0.50 + side * 0.04) * u, (0.57 + dz) * u, (0.50 + side * 0.20) * u, (0.55 + dz * 2) * u],
                   fill=_rgb((0.90, 0.86, 0.76)), width=3)
    # collar and bell
    d.arc([0.28 * u, 0.62 * u, 0.72 * u, 0.86 * u], 0, 180, fill=_rgb((0.62, 0.12, 0.14)), width=14)
    d.ellipse([0.465 * u, 0.705 * u, 0.535 * u, 0.765 * u], fill=GOLD, outline=GOLD_DARK, width=4)
    _save(im, "pharaoh")


def goblin_king():
    """The masked Duel Giant (Brier and Beauregard under the Goblin King mask)."""
    im = _canvas()
    d = ImageDraw.Draw(im)
    u = SIZE * SS
    skin = _rgb((0.36, 0.50, 0.22))
    skin_dark = _rgb((0.18, 0.28, 0.12))
    hood = _rgb((0.16, 0.10, 0.20))
    # hood
    d.polygon([(0.20 * u, 0.52 * u), (0.16 * u, 0.18 * u), (0.50 * u, 0.08 * u),
               (0.84 * u, 0.18 * u), (0.80 * u, 0.52 * u)], fill=hood, outline=_rgb((0.05, 0.04, 0.07)), width=6)
    # horns
    d.polygon([(0.24 * u, 0.26 * u), (0.12 * u, 0.10 * u), (0.33 * u, 0.16 * u)], fill=_rgb((0.78, 0.70, 0.52)),
              outline=_rgb((0.36, 0.30, 0.20)), width=4)
    d.polygon([(0.76 * u, 0.26 * u), (0.88 * u, 0.10 * u), (0.67 * u, 0.16 * u)], fill=_rgb((0.78, 0.70, 0.52)),
              outline=_rgb((0.36, 0.30, 0.20)), width=4)
    # face
    d.ellipse([0.28 * u, 0.22 * u, 0.72 * u, 0.74 * u], fill=skin, outline=skin_dark, width=6)
    # brows / eyes
    for x in (0.39, 0.61):
        d.polygon([((x - 0.06) * u, 0.38 * u), ((x + 0.06) * u, 0.34 * u), ((x + 0.05) * u, 0.42 * u),
                   ((x - 0.05) * u, 0.44 * u)], fill=_rgb((0.92, 0.70, 0.18)))
        d.ellipse([(x - 0.022) * u, 0.375 * u, (x + 0.022) * u, 0.415 * u], fill=_rgb((0.70, 0.08, 0.10)))
    # wide grin with teeth
    d.polygon([(0.38 * u, 0.55 * u), (0.62 * u, 0.55 * u), (0.58 * u, 0.63 * u), (0.42 * u, 0.63 * u)],
              fill=_rgb((0.16, 0.06, 0.07)))
    for i in range(5):
        x = 0.40 + i * 0.045
        d.polygon([(x * u, 0.55 * u), ((x + 0.035) * u, 0.55 * u), ((x + 0.017) * u, 0.585 * u)],
                  fill=CREAM)
    # collar spikes
    for x in (0.34, 0.44, 0.56, 0.66):
        d.polygon([(x * u, 0.72 * u), ((x + 0.04) * u, 0.72 * u), ((x + 0.02) * u, 0.80 * u)],
                  fill=_rgb((0.68, 0.60, 0.42)), outline=_rgb((0.30, 0.26, 0.18)), width=3)
    _save(im, "goblin_king")


def jinzo():
    """The Jinzo spirit: a dark cybernetic face with a red optic."""
    im = _canvas()
    d = ImageDraw.Draw(im)
    u = SIZE * SS
    metal = _rgb((0.20, 0.24, 0.30))
    metal_light = _rgb((0.38, 0.44, 0.52))
    metal_dark = _rgb((0.08, 0.09, 0.12))
    # skull plate
    d.rounded_rectangle([0.27 * u, 0.20 * u, 0.73 * u, 0.72 * u], radius=0.10 * u, fill=metal,
                        outline=metal_dark, width=6)
    d.rounded_rectangle([0.32 * u, 0.24 * u, 0.68 * u, 0.46 * u], radius=0.06 * u, fill=metal_light,
                        outline=metal_dark, width=4)
    # face plate
    d.rounded_rectangle([0.34 * u, 0.44 * u, 0.66 * u, 0.68 * u], radius=0.05 * u, fill=_rgb((0.14, 0.15, 0.18)),
                        outline=metal_dark, width=4)
    # optic eye
    d.ellipse([0.38 * u, 0.47 * u, 0.62 * u, 0.57 * u], fill=_rgb((0.12, 0.02, 0.03)), outline=metal_light, width=4)
    d.ellipse([0.44 * u, 0.487 * u, 0.56 * u, 0.553 * u], fill=_rgb((0.92, 0.12, 0.10)))
    d.ellipse([0.475 * u, 0.505 * u, 0.525 * u, 0.54 * u], fill=_rgb((1.0, 0.70, 0.50)))
    # mouth grille
    for i in range(5):
        x = 0.40 + i * 0.052
        d.rectangle([x * u, 0.60 * u, (x + 0.025) * u, 0.655 * u], fill=metal_dark)
    # side tubes
    for side in (-1, 1):
        x = 0.5 + side * 0.245
        d.line([(x * u, 0.30 * u), ((x + side * 0.04) * u, 0.62 * u), ((x + side * 0.02) * u, 0.78 * u)],
               fill=metal_light, width=9)
        d.line([(x * u, 0.30 * u), ((x + side * 0.04) * u, 0.62 * u), ((x + side * 0.02) * u, 0.78 * u)],
               fill=metal_dark, width=3)
    # forehead bolt
    d.rectangle([0.475 * u, 0.16 * u, 0.525 * u, 0.24 * u], fill=GOLD_DARK)
    _save(im, "jinzo")


def main():
    os.makedirs(OUT, exist_ok=True)
    narrator()
    pda()
    pharaoh()
    goblin_king()
    jinzo()
    # The PDA speaker declares a neutral expression but draws the ui_pda
    # portrait; keep an explicit pda_neutral frame so the expression path
    # resolves without relying on the portrait-id fallback.
    shutil.copyfile(os.path.join(OUT, "ui_pda.png"), os.path.join(OUT, "pda_neutral.png"))
    print("ui portraits ->", OUT)


if __name__ == "__main__":
    main()
