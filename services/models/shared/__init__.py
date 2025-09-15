"""Shared utilities for model services.

This package intentionally avoids importing heavy optional dependencies at
module import time. Import image utilities directly from
`shared.image_utils` when possible. For backward compatibility, attribute
access provides lazy imports for image helpers.
"""

from .model_utils import load_model  # noqa: F401


def __getattr__(name):  # type: ignore[override]
    # Lazy access image utility functions only when explicitly requested
    if name in {
        "prepare_image_min_size_rgb",
        "download_image_to_pil",
        "decode_base64_image_to_pil",
    }:
        from .image_utils import (
            prepare_image_min_size_rgb as _prepare_image_min_size_rgb,
            download_image_to_pil as _download_image_to_pil,
            decode_base64_image_to_pil as _decode_base64_image_to_pil,
        )
        return {
            "prepare_image_min_size_rgb": _prepare_image_min_size_rgb,
            "download_image_to_pil": _download_image_to_pil,
            "decode_base64_image_to_pil": _decode_base64_image_to_pil,
        }[name]
    raise AttributeError(f"module 'shared' has no attribute {name!r}")
