import os
import logging
from typing import Tuple, Any
from fastapi import FastAPI
from schemas import PredictRequest, PredictResponse
import sys
from pathlib import Path
_CURRENT_DIR = Path(__file__).parent
_PARENT_DIR = _CURRENT_DIR.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

app = FastAPI()

MODEL_ID = os.getenv("MODEL_ID", "distilbert-base-uncased-finetuned-sst-2-english")

sentiment_pipeline = None
model_ready = False


def load_model(model_id: str) -> Tuple[Any, Any]:
    from utils import load_model as load_generic_model
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


@app.on_event("startup")
async def startup_event():
    global sentiment_pipeline, model_ready
    from transformers import pipeline  # Lazy import

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
    sentiment_pipeline = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
    _ = sentiment_pipeline("Hello world!")
    model_ready = True

@app.get("/health")
async def health():
    return {"status": "ok", "modelReady": model_ready}


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    result = sentiment_pipeline(request.text)[0]
    # Map HF output to our schema
    return {
        "label": result["label"].lower(),
        "score": float(result["score"]),
        "modelId": MODEL_ID,
    }
