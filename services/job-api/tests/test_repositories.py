import os
import uuid
import pytest
from typing import AsyncIterator

from repository import InMemoryJobRepo, MongoJobRepo, JobRepository
from schemas import JobCreate, JobStatus, JobFilters


@pytest.fixture(
    params=[
        "memory",
        "mongo",
    ]
)
async def repo(
    request, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[JobRepository]:
    backend = request.param
    if backend == "memory":
        r: JobRepository = InMemoryJobRepo()
    else:
        if not os.getenv("MONGO_URL"):
            # Set a sensible default for local testing; reverted automatically by monkeypatch
            monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
        # Use a unique database per test to avoid leftover data
        db_name = f"jobapi_test_{uuid.uuid4().hex}"
        r = MongoJobRepo(os.getenv("MONGO_URL"), database_name=db_name)

    await r.initialize()
    try:
        yield r
    finally:
        # For Mongo backend, drop the temporary test database before closing the client
        if isinstance(r, MongoJobRepo) and r.client is not None:
            await r.client.drop_database(r.database_name)
        await r.cleanup()


@pytest.mark.asyncio
async def test_create_and_get_job(repo: JobRepository):
    payload = JobCreate(
        jobName="unit-test-job",
        username="tester",
        modelId="distilbert-base-uncased-finetuned-sst-2-english",
        input={"x": 1},
    )

    job = await repo.create_job(payload)

    assert job.id and isinstance(job.id, str)
    assert job.status == JobStatus.queued

    fetched = await repo.get_job(job.id)
    assert fetched is not None
    assert fetched.id == job.id
    assert fetched.jobName == payload.jobName


@pytest.mark.asyncio
async def test_list_jobs_basic_filters(repo: JobRepository):
    # Create jobs for filtering
    payloads = [
        JobCreate(
            jobName="a",
            username="u1",
            modelId="distilbert-base-uncased-finetuned-sst-2-english",
            input={},
        ),
        JobCreate(
            jobName="b",
            username="u1",
            modelId="distilbert-base-uncased-finetuned-sst-2-english",
            input={},
        ),
        JobCreate(
            jobName="c",
            username="u2",
            modelId="distilbert-base-uncased-finetuned-sst-2-english",
            input={},
        ),
    ]
    created_ids = []
    for p in payloads:
        j = await repo.create_job(p)
        created_ids.append(j.id)

    # Filter by username
    jobs, total = await repo.list_jobs(JobFilters(username="u1", limit=-1, offset=0))
    assert total >= 2
    assert all(j.username == "u1" for j in jobs)

    # Filter by jobName
    jobs, total = await repo.list_jobs(JobFilters(jobName="c", limit=-1, offset=0))
    assert any(j.jobName == "c" for j in jobs)


@pytest.mark.asyncio
async def test_update_and_delete_job(repo: JobRepository):
    payload = JobCreate(
        jobName="update-delete",
        username=None,
        modelId="distilbert-base-uncased-finetuned-sst-2-english",
        input={"y": 2},
    )
    job = await repo.create_job(payload)

    # Update status
    updated = await repo.update_job(job.id, {"status": JobStatus.running.value})
    assert updated is not None
    assert updated.status == JobStatus.running

    # Delete
    deleted = await repo.delete_job(job.id)
    assert deleted is True
    missing = await repo.get_job(job.id)
    assert missing is None
