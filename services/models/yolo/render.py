import io
import base64
from typing import Any, Optional
from PIL import Image


def render_result_to_base64_png(result: Any) -> Optional[str]:
    """Render an Ultralytics YOLO result to a base64-encoded PNG image.

    - Uses result.plot() to draw boxes and labels.
    - Converts BGR numpy array to RGB PIL Image and encodes as PNG base64.
    Returns None if rendering fails.
    """
    try:
        if not hasattr(result, "plot"):
            return None
        plotted = result.plot()
        if plotted is None:
            return None
        # Convert BGR to RGB
        rgb = plotted[:, :, ::-1]
        pil_img = Image.fromarray(rgb)
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None
