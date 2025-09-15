from fastapi import FastAPI, HTTPException, Depends
from schemas import Job, JobCreate, JobFilters, PaginatedJobsResponse
from repository import InMemoryJobRepo, MongoJobRepo, JobRepository
from contextlib import asynccontextmanager
import os
import logging

job_repo: JobRepository = None


def create_repository() -> JobRepository:
    """Create and return the appropriate repository based on environment variables."""
    repo_backend = os.getenv("REPO_BACKEND", "memory").lower()

    if repo_backend == "mongo":
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ValueError(
                "MONGO_URL environment variable is required when REPO_BACKEND=mongo"
            )
        return MongoJobRepo(mongo_url)
    elif repo_backend == "memory":
        return InMemoryJobRepo()
    else:
        raise ValueError(
            f"Unsupported REPO_BACKEND: {repo_backend}. Supported values: memory, mongo"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    global job_repo

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Create repository based on environment configuration
        job_repo = create_repository()
        logger.info(f"Using repository: {type(job_repo).__name__}")

        # Initialize the repository
        await job_repo.initialize()
        logger.info("Repository initialized successfully")

        yield  # Application runs here

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        # Cleanup resources
        if job_repo:
            await job_repo.cleanup()
            logger.info("Repository cleanup completed")


app = FastAPI(lifespan=lifespan)

# Extract models list to a constant for reuse
# TODO currently hard-coded, will orchestrate later
AVAILABLE_MODELS = [
    "distilbert-base-uncased-finetuned-sst-2-english",
]


@app.get("/health")
async def health():
    """Health check endpoint that includes repository status."""
    repo_healthy = await job_repo.health_check() if job_repo else False
    status = "ok" if repo_healthy else "degraded"

    return {
        "status": status,
        "repository": {
            "type": type(job_repo).__name__ if job_repo else "none",
            "healthy": repo_healthy,
        },
    }


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
