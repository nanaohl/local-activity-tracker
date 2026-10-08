"""Draws assets/AppIcon.icns. Only needed when changing the icon (requires Pillow)."""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SIZE = 1024
# Matches the timeline palette in src/web/static/common.js.
BARS = [
    (0.10, 0.20, "#2a78d6"),
    (0.32, 0.14, "#eb6834"),
    (0.48, 0.24, "#1baf7a"),
    (0.74, 0.10, "#eda100"),
]


def rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def draw_icon():
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    # Dark card with a vertical gradient, like the app's background.
    background = Image.new("RGBA", (SIZE, SIZE))
    pixels = background.load()
    top, bottom = (34, 38, 46), (18, 20, 26)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(SIZE):
            pixels[x, y] = row + (255,)
    icon.paste(background, (0, 0), rounded_mask(SIZE, int(SIZE * 0.22)))

    draw = ImageDraw.Draw(icon)
    # Clock face.
    margin, ring = SIZE * 0.26, SIZE * 0.045
    draw.ellipse([margin, margin * 0.78, SIZE - margin, SIZE - margin * 1.22], outline="#f4f6f9", width=int(ring))
    cx, cy = SIZE / 2, (margin * 0.78 + SIZE - margin * 1.22) / 2
    draw.line([cx, cy, cx, cy - SIZE * 0.14], fill="#f4f6f9", width=int(ring * 0.9))
    draw.line([cx, cy, cx + SIZE * 0.11, cy], fill="#2a9df5", width=int(ring * 0.9))

    # Timeline bar along the bottom, with coloured activity segments.
    bar_top, bar_height = SIZE * 0.78, SIZE * 0.075
    left, right = SIZE * 0.17, SIZE * 0.83
    radius = bar_height / 2
    draw.rounded_rectangle([left, bar_top, right, bar_top + bar_height], radius=radius, fill="#3a3f4a")
    span = right - left
    for start, width, color in BARS:
        x0 = left + span * start
        draw.rounded_rectangle(
            [x0, bar_top, x0 + span * width, bar_top + bar_height], radius=radius, fill=color
        )
    return icon


def main():
    icon = draw_icon()
    assets = os.path.join(PROJECT_ROOT, "assets")
    os.makedirs(assets, exist_ok=True)
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(assets, "icon.png"))

    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "AppIcon.iconset")
        os.makedirs(iconset)
        for size in (16, 32, 64, 128, 256, 512, 1024):
            icon.resize((size, size), Image.LANCZOS).save(os.path.join(iconset, f"icon_{size}x{size}.png"))
            if size > 16:
                icon.resize((size, size), Image.LANCZOS).save(
                    os.path.join(iconset, f"icon_{size // 2}x{size // 2}@2x.png")
                )
        subprocess.run(
            ["iconutil", "-c", "icns", iconset, "-o", os.path.join(assets, "AppIcon.icns")], check=True
        )
    print(f"Wrote {os.path.join(assets, 'AppIcon.icns')}")


if __name__ == "__main__":
    main()
