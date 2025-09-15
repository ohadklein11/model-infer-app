import os
import sys
import logging
import asyncio
from typing import Tuple, Any
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from schemas import PredictRequest, PredictResponse
from pathlib import Path
from contextlib import asynccontextmanager
_CURRENT_DIR = Path(__file__).parent
_PARENT_DIR = _CURRENT_DIR.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

MODEL_ID = os.getenv("MODEL_ID", "distilbert-base-uncased-finetuned-sst-2-english")
TORCH_DEVICE = os.getenv("TORCH_DEVICE", "cpu").lower()
try:
    MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", "512"))
except ValueError:
    MAX_INPUT_TOKENS = 512
try:
    REQUEST_TIMEOUT_SECONDS = float(
        os.getenv("REQUEST_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT", "10"))
    )
except ValueError:
    REQUEST_TIMEOUT_SECONDS = 10.0

sentiment_pipeline = None
tokenizer_ref = None
model_ready = False


def load_model(model_id: str) -> Tuple[Any, Any]:
    from shared.model_utils import load_model as load_generic_model
    from transformers import (
        AutoConfig,
        AutoTokenizer,
        AutoModelForSequenceClassification,
    )
    service_logger = logging.getLogger("models.distilbert")

    model, tokenizer = load_generic_model(
        model_id,
        model_from_pretrained=AutoModelForSequenceClassification.from_pretrained,
        config_from_pretrained=AutoConfig.from_pretrained,
        model_from_config=AutoModelForSequenceClassification.from_config,
        processor_from_pretrained=AutoTokenizer.from_pretrained,
        weights_dir=os.path.join(_CURRENT_DIR, "weights"),
        logger=service_logger,
    )
    return model, tokenizer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global sentiment_pipeline, tokenizer_ref, model_ready
    from transformers import pipeline  # Lazy import
    import torch

    # Configure per-service logger
    service_logger = logging.getLogger("models.distilbert")
    if not service_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)
        service_logger.addHandler(handler)
    service_logger.setLevel(logging.INFO)

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
    sentiment_pipeline = pipeline(
        "sentiment-analysis", model=model, tokenizer=tokenizer, device=device_index
    )
    tokenizer_ref = tokenizer
    _ = sentiment_pipeline("Hello world!")
    model_ready = True

    try:
        yield
    finally:
        # Best-effort cleanup
        sentiment_pipeline = None
        tokenizer_ref = None
        model_ready = False

app = FastAPI(lifespan=lifespan)

# Attach basic metrics and structured request logging via shared module
try:
    from shared.metrics import setup_basic_metrics  # type: ignore
    _metrics = setup_basic_metrics(
        app,
        model_id=MODEL_ID,
        service_name="models.distilbert",
        metrics_path="/metrics",
    )
except Exception:
    # Never fail startup if metrics wiring has an issue
    logging.getLogger("models.distilbert").warning(
        "failed to set up basic metrics", exc_info=True
    )

@app.get("/health")
async def health():
    return {"status": "ok", "modelReady": model_ready}


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    def _predict_sync(text: str) -> dict:
        if not text or not text.strip():
            raise HTTPException(status_code=422, detail="text must be non-empty")

        # Enforce token-based length limit from env
        try:
            tokens = tokenizer_ref.encode(
                text, add_special_tokens=True, truncation=False
            )
            if len(tokens) > MAX_INPUT_TOKENS:
                raise HTTPException(
                    status_code=422,
                    detail=f"input exceeds max tokens: {len(tokens)} > {MAX_INPUT_TOKENS}",
                )
        except Exception:
            # If tokenization fails for any reason, return 422 rather than crashing
            raise HTTPException(status_code=422, detail="failed to tokenize input text")

        result = sentiment_pipeline(text)[0]
        return {
            "label": result["label"].lower(),
            "score": float(result["score"]),
            "modelId": MODEL_ID,
        }

    try:
        return await asyncio.wait_for(
            run_in_threadpool(lambda: _predict_sync(request.text)),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="request timed out")
