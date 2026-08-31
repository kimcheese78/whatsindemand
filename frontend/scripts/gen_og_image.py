#!/usr/bin/env python3
"""
Generate the 1200x630 Open Graph / Twitter card image.

Output: frontend/public/og-image.png  (referenced by index.html og:image).
Re-run whenever the tagline/brand changes:  python3 scripts/gen_og_image.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = (10, 10, 10)          # #0a0a0a — matches theme-color
FG = (240, 240, 240)       # #f0f0f0
MUTED = (150, 150, 150)
ACCENT = (125, 211, 252)   # #7dd3fc — the sky-blue used on role pages

HELV = "/System/Library/Fonts/Helvetica.ttc"


def font(size, index=1):
    # Helvetica.ttc index 1 is bold-ish; fall back to default on other systems.
    try:
        return ImageFont.truetype(HELV, size, index=index)
    except Exception:
        return ImageFont.load_default()


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# thin accent rule near the top
d.rectangle([80, 96, 80 + 64, 96 + 6], fill=ACCENT)

# wordmark
d.text((80, 130), "WhatsInDemand", font=font(58, index=1), fill=FG)

# headline
d.text((80, 250), "See which skills are", font=font(76, index=1), fill=FG)
d.text((80, 336), "actually in demand", font=font(76, index=1), fill=ACCENT)

# supporting line
d.text((80, 470),
       "28,000+ live job postings, analyzed weekly across 3,300+ companies",
       font=font(30, index=0), fill=MUTED)

out = os.path.join(os.path.dirname(__file__), "..", "public", "og-image.png")
out = os.path.abspath(out)
img.save(out, "PNG")
print(f"wrote {out}  ({os.path.getsize(out)} bytes, {W}x{H})")
