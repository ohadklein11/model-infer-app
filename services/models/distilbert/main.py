from fastapi import FastAPI
import os

app = FastAPI()

MODEL_ID = os.getenv("MODEL_ID", "distilbert-base-uncased-finetuned-sst-2-english")

@app.get("/health")
async def health():
    return {"status": "ok", "modelReady": True}
