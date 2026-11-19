"""OpenCV transforms on bytes; workers never open master-side paths."""

from io import BytesIO

import cv2
import numpy as np
from PIL import Image

MAX_BYTES = 10 * 1024 * 1024


def process_image(data: bytes, operation: str, parameters: dict) -> bytes:
    try:
        return _process_image(data, operation, parameters)
    except cv2.error as exc:
        raise ValueError("OpenCV image processing failed") from exc


def _process_image(data: bytes, operation: str, parameters: dict) -> bytes:
    image = _decode_image(data)
    result = _apply_operation(image, operation, parameters)
    return _encode_png(result)


def _decode_image(data: bytes) -> np.ndarray:
    """Validate byte/header limits before decoding pixels with OpenCV."""
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Invalid image byte length")
    with Image.open(BytesIO(data)) as header:
        width, height = header.size
        if (header.format not in {"PNG", "JPEG"}
                or max(width, height) > 4096 or width * height > 16_000_000):
            raise ValueError("Unsupported image format or dimensions")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("OpenCV could not decode image")
    return image


def _apply_operation(image: np.ndarray, operation: str, parameters: dict) -> np.ndarray:
    """Apply one supported operation with the existing parameter limits."""
    if operation == "grayscale":
        result = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif operation == "resize":
        width, height = parameters["width"], parameters["height"]
        if (type(width) is not int or type(height) is not int
                or not (1 <= width <= 4096 and 1 <= height <= 4096)
                or width * height > 16_000_000):
            raise ValueError("Invalid resize dimensions")
        result = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    elif operation == "gaussian_blur":
        kernel = parameters.get("kernel_size", 5)
        if type(kernel) is not int or not 1 <= kernel <= 99 or kernel % 2 != 1:
            raise ValueError("Invalid Gaussian kernel")
        result = cv2.GaussianBlur(image, (kernel, kernel), 0)
    elif operation == "edge_detection":
        low, high = parameters.get("threshold1", 100), parameters.get("threshold2", 200)
        if type(low) is not int or type(high) is not int or not 0 <= low <= high <= 255:
            raise ValueError("Invalid edge thresholds")
        result = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), low, high)
    else:
        raise ValueError("Unsupported image operation")
    return result


def _encode_png(result: np.ndarray) -> bytes:
    """Return PNG bytes only when encoding succeeds within the byte limit."""
    ok, encoded = cv2.imencode(".png", result)
    if not ok or len(encoded) > MAX_BYTES:
        raise ValueError("Failed to encode output within 10 MiB")
    return encoded.tobytes()
