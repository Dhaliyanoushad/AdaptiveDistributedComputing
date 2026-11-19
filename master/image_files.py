"""Bounded image validation and server-owned file storage."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_SIDE = 4096


def inspect_image(data: bytes, png_only: bool = False) -> tuple[int, int, str]:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Image must contain 1 byte to 10 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ({"PNG"} if png_only else {"JPEG", "PNG"}):
                    raise ValueError("Only JPEG/PNG image content is accepted")
                width, height = image.size
                if max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
                    raise ValueError("Image exceeds 4096 pixels per side or 16 million pixels")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Animated images are not supported")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
                return width, height, image.mode
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Invalid or unsafe image") from exc


def save_unique(directory: Path, data: bytes, suffix: str) -> Path:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}{suffix}"
    try:
        with path.open("xb") as output:
            output.write(data)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path
