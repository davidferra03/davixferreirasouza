from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


def fit_three_by_four(source: Path, destination: Path, mode: str = "pad") -> Path:
    """Create a 3:4 image without stretching; EXIF orientation is honored."""
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        width, height = image.size
        target_ratio = 3 / 4
        ratio = width / height
        if mode == "crop":
            if ratio > target_ratio:
                new_width = round(height * target_ratio)
                left = (width - new_width) // 2
                image = image.crop((left, 0, left + new_width, height))
            elif ratio < target_ratio:
                new_height = round(width / target_ratio)
                top = (height - new_height) // 2
                image = image.crop((0, top, width, top + new_height))
        else:
            if ratio > target_ratio:
                canvas_size = (width, round(width / target_ratio))
            else:
                canvas_size = (round(height * target_ratio), height)
            background = image.resize((1, 1)).resize(canvas_size)
            background = background.filter(ImageFilter.GaussianBlur(24))
            background.paste(image, ((canvas_size[0] - width) // 2, (canvas_size[1] - height) // 2))
            image = background
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="JPEG", quality=95, optimize=True)
    return destination
