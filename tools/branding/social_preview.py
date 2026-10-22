"""Render the GitHub social preview (1280x640 PNG) from the light banner SVG.

GitHub shows this image when the repository is shared on social networks and in
search results. The API cannot set it: upload the file by hand under the
repository Settings, "Social preview".

Requires ``rsvg-convert`` (librsvg) on the PATH and Pillow (installed with the
``viz`` extra through matplotlib).

    python tools/branding/social_preview.py
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

BRANDING = Path(__file__).resolve().parents[2] / "docs" / "images" / "branding"
BANNER = BRANDING / "banner-light.svg"
OUTPUT = BRANDING / "social-preview.png"
WIDTH, HEIGHT = 1280, 640
BACKGROUND = (247, 248, 255)


def render_banner(width: int) -> Image.Image:
    """Rasterise the banner at ``width`` pixels with librsvg."""
    converter = shutil.which("rsvg-convert")
    if converter is None:
        sys.exit(
            "rsvg-convert not found: install librsvg (e.g. apt install librsvg2-bin)"
        )
    png = subprocess.run(
        [converter, "-w", str(width), str(BANNER)],
        check=True,
        capture_output=True,
    ).stdout
    return Image.open(io.BytesIO(png)).convert("RGBA")


def compose(banner: Image.Image) -> Image.Image:
    """Centre the banner vertically on a 1280x640 canvas."""
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (*BACKGROUND, 255))
    top = (HEIGHT - banner.height) // 2
    canvas.alpha_composite(banner, (0, top))
    return canvas.convert("RGB")


def main() -> None:
    """Write the social preview next to the SVGs."""
    image = compose(render_banner(WIDTH))
    image.save(OUTPUT, optimize=True)
    print(f"{OUTPUT.relative_to(BRANDING.parents[2])}  {image.width}x{image.height}")


if __name__ == "__main__":
    main()
