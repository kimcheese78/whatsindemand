#!/usr/bin/env python3
"""
Generate the 1200x630 Open Graph / Twitter card image.

The card design lives in `og-image.html` (edit that to change the look).
This script renders it with headless Chrome at 2x and downscales to 1200x630
for a crisp result.

Output: frontend/public/og-image.png  (referenced by index.html og:image).
Re-run whenever the tagline/brand changes:  python3 scripts/gen_og_image.py
"""
import os
import subprocess
import tempfile
from PIL import Image

W, H = 1200, 630
HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "og-image.html")
OUT = os.path.abspath(os.path.join(HERE, "..", "public", "og-image.png"))

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    raise SystemExit("Chrome not found — install Chrome or edit CHROME_CANDIDATES.")


def main():
    chrome = find_chrome()
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "raw.png")
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=2", f"--window-size={W},{H}",
             f"--screenshot={raw}", f"file://{HTML}"],
            check=True, capture_output=True,
        )
        # rendered at 2x — downscale for crisp text
        Image.open(raw).resize((W, H), Image.LANCZOS).save(OUT, "PNG")

    print(f"wrote {OUT}  ({os.path.getsize(OUT)} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
