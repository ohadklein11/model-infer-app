from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from schemas import Job, JobCreate, JobFilters, JobStatus
from datetime import datetime, timezone
import uuid


class JobRepository(ABC):
    """
    Abstract base class defining the interface for job storage operations.

    This interface allows swapping between different storage backends
    (in-memory, MongoDB, etc.) without changing the business logic.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the repository (create indexes, connections, etc.).

        This method should be called once during application startup.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the repository backend is healthy and accessible.

        Returns:
            True if backend is healthy, False otherwise
        """
        pass

    @abstractmethod
    async def create_job(self, job_data: JobCreate) -> Job:
        """
        Create a new job and return it with generated ID and timestamps.

        Args:
            job_data: The job creation payload

        Returns:
            The created job with ID, timestamps, and initial status

        Raises:
            ValueError: If job_data is invalid
        """
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieve a job by its ID.

        Args:
            job_id: The unique job identifier

        Returns:
            The job if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_jobs(self, filters: JobFilters) -> Tuple[List[Job], int]:
        """
        List jobs with filtering and pagination.

        Args:
            filters: Query filters including pagination parameters

        Returns:
            Tuple of (jobs_list, total_count)
            - jobs_list: The filtered and paginated jobs
            - total_count: Total number of jobs matching filters (before pagination)
        """
        pass

    @abstractmethod
    async def update_job(self, job_id: str, updates: dict) -> Optional[Job]:
        """
        Update specific fields of a job.

        Args:
            job_id: The unique job identifier
            updates: Dictionary of fields to update (e.g., {"status": "completed", "result": {...}})

        Returns:
            The updated job if found, None otherwise

        Note:
            Should automatically update the updatedAt timestamp
        """
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a job by its ID.

        Args:
            job_id: The unique job identifier

        Returns:
            True if job was deleted, False if job was not found
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Clean up resources (close connections, etc.).

        This method should be called during application shutdown.
        """
        pass


class InMemoryJobRepo(JobRepository):
    """
    In-memory implementation of JobRepository using a Python dictionary.

    This implementation stores jobs in memory and loses data on restart.
    Useful for development and testing.
    """

    def __init__(self):
        self._jobs: dict[str, Job] = {}

    async def initialize(self) -> None:
        """Initialize the in-memory repository (no-op for memory storage)."""
        pass

    async def health_check(self) -> bool:
        """In-memory storage is always healthy."""
        return True

    async def create_job(self, job_data: JobCreate) -> Job:
        """Create a new job with generated ID and timestamps."""
        now = datetime.now(timezone.utc)
        job = Job(
            id=str(uuid.uuid4()),
            jobName=job_data.jobName,
            username=job_data.username,
            modelId=job_data.modelId,
            input=job_data.input,
            status=JobStatus.queued,
            result=None,
            error=None,
            createdAt=now,
            updatedAt=now,
        )
        self._jobs[job.id] = job
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by its ID."""
        return self._jobs.get(job_id)

    async def list_jobs(self, filters: JobFilters) -> Tuple[List[Job], int]:
        """List jobs with filtering and pagination."""
        jobs = list(self._jobs.values())
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

        limit, offset = filters.get_pagination()
        if limit is None:
            paginated_jobs = jobs[offset:]
        else:
            paginated_jobs = jobs[offset : offset + limit]

        return paginated_jobs, total_count

    async def update_job(self, job_id: str, updates: dict) -> Optional[Job]:
        """Update specific fields of a job."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        # Create a new job instance with updates
        job_dict = job.model_dump()
        job_dict.update(updates)
        job_dict["updatedAt"] = datetime.now(timezone.utc)

        updated_job = Job(**job_dict)
        self._jobs[job_id] = updated_job
        return updated_job

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job by its ID."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    async def cleanup(self) -> None:
        """Clean up resources (no-op for memory storage)."""
        pass
