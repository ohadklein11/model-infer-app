import os
import sys
import logging
import asyncio
import torch
from typing import Any, List
from PIL import Image
from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from schemas import PredictRequest, PredictResponse
from pathlib import Path
from contextlib import asynccontextmanager

_CURRENT_DIR = Path(__file__).parent
_PARENT_DIR = _CURRENT_DIR.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

# Configure per-service logger once at module import
service_logger = logging.getLogger("models.yolo")
if not service_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    service_logger.addHandler(handler)
service_logger.setLevel(logging.INFO)

MODEL_WEIGHTS = os.getenv("MODEL_WEIGHTS", "yolo11n.pt")
TORCH_DEVICE = os.getenv("TORCH_DEVICE", "cpu").lower()
try:
    REQUEST_TIMEOUT_SECONDS = float(
        os.getenv("REQUEST_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT", "10"))
    )
except ValueError:
    REQUEST_TIMEOUT_SECONDS = 10.0

yolo_model: Any | None = None
model_ready = False
_device_index: int = -1


def load_model(weights_path: str) -> Any:
    """Load Ultralytics YOLO model for detection using pretrained weights.

    Raises if non-detection weights (e.g., -seg or -pose) are provided.
    """
    from ultralytics import YOLO

    lower = weights_path.lower()
    if lower.endswith("-seg.pt") or lower.endswith("-pose.pt"):
        raise ValueError(
            "Non-detection YOLO weights provided. Use detection weights like yolo11n.pt, yolo11s.pt, etc."
        )
    model = YOLO(weights_path)
    return model


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global yolo_model, model_ready, _device_index

    # Select device based on env
    if TORCH_DEVICE == "cuda":
        if torch.cuda.is_available():
            _device_index = 0
        else:
            service_logger.warning(
                "TORCH_DEVICE=cuda requested but CUDA is not available; falling back to CPU"
            )
            _device_index = -1
    else:
        _device_index = -1

    # Load model
    try:
        yolo_model = load_model(MODEL_WEIGHTS)
    except Exception:
        service_logger.exception("failed to load YOLO model")
        raise

    # Warmup on a dummy image
    try:
        from shared import download_image_to_pil
        warmup_image, _ = download_image_to_pil("https://ultralytics.com/images/bus.jpg", timeout_seconds=5.0)
    except Exception:
        warmup_image = Image.new("RGB", (640, 640), color=(200, 200, 200))
    try:
        device_arg: Any = _device_index if _device_index >= 0 else "cpu"
        _ = yolo_model.predict(warmup_image, verbose=False, device=device_arg)
    except Exception:
        service_logger.warning("YOLO warmup inference failed", exc_info=True)

    model_ready = True

    try:
        yield
    finally:
        # Best-effort cleanup
        yolo_model = None
        model_ready = False


app = FastAPI(lifespan=lifespan)

# Attach basic metrics and structured request logging via shared module
try:
    from shared.metrics import setup_basic_metrics  # type: ignore
    _metrics = setup_basic_metrics(
        app,
        model_id=MODEL_WEIGHTS,
        service_name="models.yolo",
        metrics_path="/metrics",
    )
except Exception:
    # Never fail startup if metrics wiring has an issue
    logging.getLogger("models.yolo").warning(
        "failed to set up basic metrics", exc_info=True
    )


@app.get("/health")
async def health():
    return {"status": "ok", "modelReady": model_ready}


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest, render: bool = Query(default=False, description="If true, return base64 PNG with drawn boxes")):
    def _predict_sync(req: PredictRequest) -> dict:
        # Prepare image input: base64 image or URL
        image_input: Any
        image_bytes: int | None = None
        if req.imageBase64:
            try:
                from shared import decode_base64_image_to_pil, prepare_image_min_size_rgb
                out = decode_base64_image_to_pil(req.imageBase64)
                if isinstance(out, tuple):
                    img, image_bytes = out
                else:
                    img, image_bytes = out, None
                image_input = prepare_image_min_size_rgb(img)
            except Exception:
                raise HTTPException(status_code=422, detail="invalid imageBase64 payload")
        elif req.imageUrl:
            try:
                from shared import download_image_to_pil, prepare_image_min_size_rgb
                out = download_image_to_pil(req.imageUrl, timeout_seconds=10.0)
                if isinstance(out, tuple):
                    img, image_bytes = out
                else:
                    img, image_bytes = out, None
                image_input = prepare_image_min_size_rgb(img)
            except Exception:
                raise HTTPException(status_code=422, detail="failed to download imageUrl")
        else:
            raise HTTPException(status_code=422, detail="either imageBase64 or imageUrl is required")

        # Log observability details for the resolved image
        try:
            width, height = getattr(image_input, "size", (None, None))
            service_logger.info(
                f"imageInputResolved bytes={image_bytes if image_bytes is not None else -1} size={width}x{height}"
            )
        except Exception:
            pass

        # Run YOLO detection
        try:
            device_arg: Any = _device_index if _device_index >= 0 else "cpu"
            results = yolo_model.predict(image_input, verbose=False, device=device_arg)  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"model inference failed: {str(e)}")

        if not results:
            return {"boxes": [], "scores": [], "modelId": MODEL_WEIGHTS, "imageBase64": None}

        res = results[0]
        # Extract predictions
        boxes_xyxy: List[List[float]] = []
        scores: List[float] = []
        classes: List[int] = []

        def _to_list(x: Any) -> List[Any]:
            try:
                # torch.Tensor
                if hasattr(x, "cpu"):
                    x = x.cpu()
                if hasattr(x, "numpy"):
                    x = x.numpy()
                if hasattr(x, "tolist"):
                    return x.tolist()
                # numpy array falls back here
                if isinstance(x, list):
                    return x
                return [x]
            except Exception:
                return []

        try:
            if hasattr(res, "boxes") and res.boxes is not None:
                if getattr(res.boxes, "xyxy", None) is not None:
                    boxes_xyxy = _to_list(res.boxes.xyxy)
                if getattr(res.boxes, "conf", None) is not None:
                    scores = [float(s) for s in _to_list(res.boxes.conf)]
                if getattr(res.boxes, "cls", None) is not None:
                    classes = [int(c) for c in _to_list(res.boxes.cls)]
        except Exception:
            service_logger.warning("failed to parse YOLO outputs", exc_info=True)

        # Map class indices to labels
        names = None
        try:
            names = res.names if hasattr(res, "names") else None
            if names is None and hasattr(yolo_model, "names"):
                names = getattr(yolo_model, "names")
        except Exception:
            names = None

        boxes_resp = []
        for i, xyxy in enumerate(boxes_xyxy):
            xmin, ymin, xmax, ymax = xyxy
            label: str
            if isinstance(names, dict):
                cls_idx = classes[i] if i < len(classes) else -1
                label = names.get(cls_idx, str(cls_idx))
            else:
                label = str(classes[i]) if i < len(classes) else "unknown"
            boxes_resp.append(
                {
                    "label": label,
                    "box": {
                        "xmin": float(xmin),
                        "xmax": float(xmax),
                        "ymin": float(ymin),
                        "ymax": float(ymax),
                    },
                }
            )

        resp: dict = {"boxes": boxes_resp, "scores": scores, "modelId": MODEL_WEIGHTS}
        if render:
            try:
                from render import render_result_to_base64_png
                resp["imageBase64"] = render_result_to_base64_png(res)
            except Exception:
                service_logger.warning("failed to render plotted image", exc_info=True)
                resp["imageBase64"] = None
        else:
            resp["imageBase64"] = None

        return resp

    try:
        return await asyncio.wait_for(
            run_in_threadpool(lambda: _predict_sync(request)),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="request timed out")
