from fastapi import FastAPI
from schemas import Job, JobCreate, JobStatus
from datetime import datetime, timezone
import uuid

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/models")
def list_models() -> list[str]:
    return [
        "distilbert-base-uncased-finetuned-sst-2-english",
    ]


@app.post("/jobs", response_model=Job)
def create_job(payload: JobCreate) -> Job:
    """
    Create a new job.

    Example:
        curl -X POST http://localhost:8080/jobs \
          -H 'Content-Type: application/json' \
          -d '{"jobName":"example-job","username":"alice","modelId":"distilbert-base-uncased-finetuned-sst-2-english","input":{"text":"I love this!"}}'

    Response:
        {
          "id": "fd9263bc-dae8-4004-9fcf-8d83ebf2bf8a",
          "jobName": "sentiment-analysis",
          "username": "alice",
          "modelId": "distilbert-base-uncased-finetuned-sst-2-english",
          "input": {"text": "I love this!"},
          "status": "queued",
          "result": null,
          "error": null,
          "createdAt": "2025-09-12T07:19:20.367483Z",
          "updatedAt": "2025-09-12T07:19:20.367483Z"
        }
    """
    now = datetime.now(timezone.utc)
    return Job(
        id=str(uuid.uuid4()),
        jobName=payload.jobName,
        username=payload.username,
        modelId=payload.modelId,
        input=payload.input,
        status=JobStatus.queued,
        result=None,
        error=None,
        createdAt=now,
        updatedAt=now,
    )