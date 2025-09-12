from fastapi import FastAPI, HTTPException, Depends
from schemas import Job, JobCreate, JobStatus, JobFilters
from datetime import datetime, timezone
import uuid

app = FastAPI()

jobs_db = {}  # will be later replaced with a db

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
    """
    now = datetime.now(timezone.utc)
    job = Job(
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
    jobs_db[job.id] = job
    return job

@app.get("/jobs", response_model=list[Job])
def list_jobs(filters: JobFilters = Depends(JobFilters)) -> list[Job]:
    jobs = list(jobs_db.values())
    if filters.q:
        jobs = [job for job in jobs if filters.q in job.jobName or filters.q in job.username]
    if filters.username:
        jobs = [job for job in jobs if job.username == filters.username]
    if filters.jobName:
        jobs = [job for job in jobs if job.jobName == filters.jobName]
    if filters.status:
        jobs = [job for job in jobs if job.status == filters.status]
    return jobs

@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]
