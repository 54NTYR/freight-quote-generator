"""Generate a compact build/app-icon.ico for Windows exe/installer."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static" / "img" / "app-icon.png"
OUTPUT = ROOT / "build" / "app-icon.ico"
SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def load_clean_icon(size: int = 256) -> Image.Image:
    image = Image.open(SOURCE).convert("RGBA")
    image = image.resize((size, size), Image.Resampling.LANCZOS)

    # Re-draw onto a fresh bitmap so Pillow writes a compact ICO.
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(image, (0, 0))
    return canvas


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"App icon not found: {SOURCE}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    icon = load_clean_icon(256)
    icon.save(OUTPUT, format="ICO", sizes=SIZES)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Created {OUTPUT} ({size_kb:.1f} KB)")
    if size_kb > 250:
        raise RuntimeError("Generated icon is too large for Inno Setup (max ~256 KB).")


if __name__ == "__main__":
    main()
