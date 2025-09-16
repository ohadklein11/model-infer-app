import os
import sys
import logging
import asyncio
import torch
from typing import Tuple, Any
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from schemas import PredictRequest, PredictResponse
from pathlib import Path
from contextlib import asynccontextmanager
_CURRENT_DIR = Path(__file__).parent
_PARENT_DIR = _CURRENT_DIR.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

# Configure per-service logger once at module import
service_logger = logging.getLogger("models.vqa")
if not service_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    service_logger.addHandler(handler)
service_logger.setLevel(logging.INFO)

MODEL_ID = os.getenv("MODEL_ID", "dandelin/vilt-b32-finetuned-vqa")
TORCH_DEVICE = os.getenv("TORCH_DEVICE", "cpu").lower()
try:
    MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", "2048"))
except ValueError:
    MAX_INPUT_TOKENS = 2048
try:
    REQUEST_TIMEOUT_SECONDS = float(
        os.getenv("REQUEST_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT", "10"))
    )
except ValueError:
    REQUEST_TIMEOUT_SECONDS = 10.0

vqa_pipeline = None
tokenizer_ref = None
model_ready = False


def load_model(model_id: str) -> Tuple[Any, Any]:
    """Load VQA model with simple local state_dict caching."""
    from transformers import (
        AutoConfig,
        AutoTokenizer,
        AutoModelForVisualQuestionAnswering,
    )

    from shared.model_utils import load_model as load_model_shared
    model, tokenizer = load_model_shared(model_id,
        model_from_pretrained=AutoModelForVisualQuestionAnswering.from_pretrained,
        config_from_pretrained=AutoConfig.from_pretrained,
        model_from_config=AutoModelForVisualQuestionAnswering.from_config,
        processor_from_pretrained=AutoTokenizer.from_pretrained,
        weights_dir=os.path.join(_CURRENT_DIR, "weights"),
        save_weights=True,
        logger=service_logger,
    )
    return model, tokenizer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global vqa_pipeline, tokenizer_ref, model_ready
    from transformers import pipeline, AutoProcessor  # Lazy import

    model, tokenizer = load_model(MODEL_ID)

    # Select device based on env
    if TORCH_DEVICE == "cuda":
        if torch.cuda.is_available():
            device_index = 0
            device = torch.device("cuda")
        else:
            service_logger.warning(
                "TORCH_DEVICE=cuda requested but CUDA is not available; falling back to CPU"
            )
            device_index = -1
            device = torch.device("cpu")
    else:
        device_index = -1
        device = torch.device("cpu")

    model.to(device)
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    vqa_pipeline = pipeline(
        "visual-question-answering",
        model=model,
        tokenizer=processor.tokenizer,
        image_processor=processor.image_processor,
        device=device_index,
    )
    tokenizer_ref = processor.tokenizer
    random_image_url = "https://placehold.co/600x400"
    try:
        from shared import download_image_to_pil
        warmup_image, _ = download_image_to_pil(random_image_url, timeout_seconds=5.0)
    except Exception:
        warmup_image = Image.new("RGB", (600, 400), color=(200, 200, 200))
    _ = vqa_pipeline(image=warmup_image, question="What is this image?")
    model_ready = True

    try:
        yield
    finally:
        # Best-effort cleanup
        vqa_pipeline = None
        tokenizer_ref = None
        model_ready = False

app = FastAPI(lifespan=lifespan)

# Attach basic metrics and structured request logging via shared module
try:
    from shared.metrics import setup_basic_metrics  # type: ignore
    _metrics = setup_basic_metrics(
        app,
        model_id=MODEL_ID,
        service_name="models.vqa",
        metrics_path="/metrics",
    )
except Exception:
    # Never fail startup if metrics wiring has an issue
    logging.getLogger("models.vqa").warning(
        "failed to set up basic metrics", exc_info=True
    )

@app.get("/health")
async def health():
    return {"status": "ok", "modelReady": model_ready}


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    def _predict_sync(req: PredictRequest) -> dict:

        question = (req.question or "").strip()
        if not question:
            raise HTTPException(status_code=422, detail="question must be non-empty")

        # Enforce token-based length limit from env on the question
        try:
            tokens = tokenizer_ref.encode(question, add_special_tokens=True, truncation=False)
            if len(tokens) > MAX_INPUT_TOKENS:
                raise HTTPException(
                    status_code=422,
                    detail=f"question exceeds max tokens: {len(tokens)} > {MAX_INPUT_TOKENS}",
                )
        except Exception:
            raise HTTPException(status_code=422, detail="failed to tokenize question")

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

        try:
            outputs = vqa_pipeline(image=image_input, question=question)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"model inference failed: {str(e)}")

        # Handle pipeline outputs for both classification-style ('answer') and generative ('generated_text') models
        result = outputs[0] if isinstance(outputs, list) else outputs
        answer = None
        score = None
        if isinstance(result, dict):
            answer = result.get("answer") or result.get("generated_text")
            score = result.get("score")
        if answer is None:
            # Fallback to string casting
            answer = str(result)
        if score is None:
            score = 1.0

        return {
            "answer": answer,
            "score": float(score),
            "modelId": MODEL_ID,
        }

    try:
        return await asyncio.wait_for(
            run_in_threadpool(lambda: _predict_sync(request)),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="request timed out")
