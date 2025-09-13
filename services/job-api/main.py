from fastapi import FastAPI, HTTPException, Depends
from schemas import Job, JobCreate, JobFilters, PaginatedJobsResponse
from repository import InMemoryJobRepo, JobRepository
from contextlib import asynccontextmanager

job_repo: JobRepository = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    global job_repo
    job_repo = InMemoryJobRepo()
    await job_repo.initialize()
    yield  # will return when the context manager is exited
    await job_repo.cleanup()


app = FastAPI(lifespan=lifespan)

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
async def create_job(payload: JobCreate) -> Job:
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

    job = await job_repo.create_job(payload)
    return job


@app.get("/jobs", response_model=PaginatedJobsResponse)
async def list_jobs(filters: JobFilters = Depends(JobFilters)) -> PaginatedJobsResponse:
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

    paginated_jobs, total_count = await job_repo.list_jobs(filters)

    # Calculate has_more based on pagination
    if limit is None:
        has_more = False
        limit = len(paginated_jobs)
    else:
        has_more = offset + limit < total_count

    return PaginatedJobsResponse(
        jobs=paginated_jobs,
        total=total_count,
        limit=limit,
        offset=offset,
        hasMore=has_more,
    )


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    job = await job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with id '{job_id}' not found")
    return job


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> dict:
    """Delete a job by ID. For testing purposes only."""
    deleted = await job_repo.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job with id '{job_id}' not found")
    return {"message": f"Job {job_id} deleted successfully"}
