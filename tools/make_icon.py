"""Génère les images de syncausha/assets : icône de l'application (icon.png, icon.ico) et petits
pictogrammes de la feuille de style (check.png, chevron_down.png, chevron_up.png)."""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "syncausha" / "assets"
GLYPH_SIZE = 32  # net une fois réduit par Qt, y compris sur les écrans haute densité
SUPERSAMPLING = 8  # dessin agrandi puis réduit : bords lissés
CHECK_COLOR = (255, 255, 255, 255)
CHEVRON_COLOR = (0x8A, 0x89, 0x84, 255)  # gris moyen lisible sur les thèmes clair et sombre


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


def stroke(points: list[tuple[float, float]], width: float, color: tuple[int, int, int, int]) -> Image.Image:
    """Trait à bouts et angles arrondis, sur fond transparent (coordonnées pour GLYPH_SIZE)."""
    scale = SUPERSAMPLING
    big = Image.new("RGBA", (GLYPH_SIZE * scale, GLYPH_SIZE * scale), color[:3] + (0,))
    pen = ImageDraw.Draw(big)
    scaled = [(x * scale, y * scale) for x, y in points]
    pen.line(scaled, fill=color, width=round(width * scale), joint="curve")
    radius = width * scale / 2
    for x, y in (scaled[0], scaled[-1]):
        pen.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    return big.resize((GLYPH_SIZE, GLYPH_SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    image = draw()
    image.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / "icon.png")
    image.save(ASSETS / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    stroke([(7, 16.5), (13, 22.5), (25, 10)], 4, CHECK_COLOR).save(ASSETS / "check.png")
    chevron = stroke([(6, 11), (16, 21), (26, 11)], 4, CHEVRON_COLOR)
    chevron.save(ASSETS / "chevron_down.png")
    chevron.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(ASSETS / "chevron_up.png")


if __name__ == "__main__":
    main()
