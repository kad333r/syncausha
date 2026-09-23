"""Génère syncausha/assets/icon.png et icon.ico (carré bleu arrondi + onde sonore)."""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "syncausha" / "assets"


def draw(size: int = 512) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=(47, 111, 219, 255))
    bars = [0.35, 0.6, 0.85, 0.6, 0.35]
    bar_width, gap = size // 12, size // 18
    x = (size - (len(bars) * bar_width + (len(bars) - 1) * gap)) // 2
    for height in bars:
        bar_height = int(size * 0.55 * height)
        top = (size - bar_height) // 2
        pen.rounded_rectangle((x, top, x + bar_width, top + bar_height), radius=bar_width // 2, fill="white")
        x += bar_width + gap
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    image = draw()
    image.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / "icon.png")
    image.save(ASSETS / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
