from fastapi import FastAPI, HTTPException, Depends
from schemas import Job, JobCreate, JobStatus, JobFilters, PaginatedJobsResponse
from datetime import datetime, timezone
import uuid

app = FastAPI()

jobs_db = {}  # will be later replaced with a db

# Extract models list to a constant for reuse
AVAILABLE_MODELS = [
    "distilbert-base-uncased-finetuned-sst-2-english",
]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/models")
def list_models() -> list[str]:
    return AVAILABLE_MODELS


@app.post("/jobs", response_model=Job)
def create_job(payload: JobCreate) -> Job:
    """
    Create a new job.
    """
    if payload.modelId not in AVAILABLE_MODELS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid modelId '{payload.modelId}'. Available models: {AVAILABLE_MODELS}",
        )

    if not payload.input:
        raise HTTPException(status_code=422, detail="Input cannot be empty")

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


@app.get("/jobs", response_model=PaginatedJobsResponse)
def list_jobs(filters: JobFilters = Depends(JobFilters)) -> PaginatedJobsResponse:
    """
    List jobs with filtering and pagination support.

    Supports two pagination approaches:
    1. Page-based: ?page=1&pageSize=10
    2. Offset-based: ?limit=10&offset=0
    """
    try:
        limit, offset = filters.get_pagination()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    jobs = list(jobs_db.values())
    if filters.q:
        jobs = [
            job
            for job in jobs
            if filters.q.lower() in job.jobName.lower()
            or (job.username and filters.q.lower() in job.username.lower())
        ]
    if filters.username:
        jobs = [job for job in jobs if job.username == filters.username]
    if filters.jobName:
        jobs = [job for job in jobs if job.jobName == filters.jobName]
    if filters.status:
        jobs = [job for job in jobs if job.status == filters.status]

    jobs.sort(key=lambda x: x.createdAt, reverse=True)
    total_count = len(jobs)

    # Handle unlimited results (limit=-1 becomes None)
    if limit is None:
        # No limit - return all results from offset
        paginated_jobs = jobs[offset:]
        has_more = False
        limit = len(paginated_jobs)
    else:
        # Normal pagination
        paginated_jobs = jobs[offset : offset + limit]
        has_more = offset + limit < total_count
    return PaginatedJobsResponse(
        jobs=paginated_jobs,
        total=total_count,
        limit=limit,
        offset=offset,
        hasMore=has_more,
    )


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail=f"Job with id '{job_id}' not found")
    return jobs_db[job_id]


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    """Delete a job by ID. For testing purposes only."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail=f"Job with id '{job_id}' not found")

    del jobs_db[job_id]
    return {"message": f"Job {job_id} deleted successfully"}
