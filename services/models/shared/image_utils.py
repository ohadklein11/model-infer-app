import base64
from io import BytesIO

import requests
from PIL import Image


def prepare_image_min_size_rgb(image: Image.Image, *, min_side: int = 32) -> Image.Image:
    """Ensure image is RGB and has at least min_side on the smallest dimension."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    width, height = image.size
    smallest = min(width, height)
    if smallest < min_side:
        scale = float(min_side) / float(smallest)
        new_w = max(min_side, int(round(width * scale)))
        new_h = max(min_side, int(round(height * scale)))
        image = image.resize((new_w, new_h), resample=Image.BILINEAR)
    return image


def download_image_to_pil(url: str, *, timeout_seconds: float = 10.0) -> tuple[Image.Image, int]:
    """Download an image and return (PIL Image RGB, original bytes length)."""
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    content = response.content
    image = Image.open(BytesIO(content)).convert("RGB")
    return image, len(content)


def decode_base64_image_to_pil(b64_data: str) -> tuple[Image.Image, int]:
    """Decode base64 image data and return (PIL Image RGB, decoded bytes length)."""
    data = b64_data
    if "," in data and ";base64" in data.split(",", 1)[0]:
        data = data.split(",", 1)[1]
    image_bytes = base64.b64decode(data)
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    return image, len(image_bytes)
