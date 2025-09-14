from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from schemas import Job, JobCreate, JobFilters, JobStatus
from datetime import datetime, timezone
import uuid
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorCollection,
)
import logging
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError


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


class MongoJobRepo(JobRepository):
    """
    MongoDB implementation of JobRepository using Motor (async MongoDB driver).

    This implementation provides persistent storage with proper indexing
    for efficient queries and scalable performance.
    """

    ID_GENERATION_MAX_RETRIES = 100
    SERVER_SELECTION_TIMEOUT_MS = 5000  # 5 seconds
    CONNECT_TIMEOUT_MS = 10000  # 10 seconds
    MAX_POOL_SIZE = 10

    def __init__(self, mongo_url: str, database_name: str = "jobapi"):
        self.mongo_url = mongo_url
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.jobs_collection: Optional[AsyncIOMotorCollection] = None
        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> None:
        """Initialize MongoDB connection and create indexes."""
        try:
            self.client = AsyncIOMotorClient(
                self.mongo_url,
                serverSelectionTimeoutMS=self.SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=self.CONNECT_TIMEOUT_MS,
                maxPoolSize=self.MAX_POOL_SIZE,
            )
            await self.client.admin.command("ping")
            self.logger.info(f"Connected to MongoDB at {self.mongo_url}")

            self.db = self.client[self.database_name]
            self.jobs_collection = self.db.jobs
            await self._create_indexes()
        except Exception as e:
            self.logger.error(f"Failed to initialize MongoDB connection: {e}")
            raise

            self.logger.info(f"Connected to MongoDB at {self.mongo_url}")

            self.db = self.client[self.database_name]
            self.jobs_collection = self.db.jobs
            await self._create_indexes()
        except Exception as e:
            self.logger.error(f"Failed to initialize MongoDB connection: {e}")
            raise

    async def _create_indexes(self) -> None:
        """
        Create database indexes for optimal query performance.
        Indexes:
            - id: Unique index on job ID
            - username: Index on username for user-specific queries
            - jobName: Index on jobName for filtering
            - status: Index on status for filtering
            - createdAt: Index on createdAt for sorting (descending for most recent first)
            - idx_user_status_created: Compound index for common query pattern (username + status + createdAt)
        """
        try:
            await self.jobs_collection.create_index("username", name="idx_username")
            await self.jobs_collection.create_index("jobName", name="idx_job_name")
            await self.jobs_collection.create_index("status", name="idx_status")
            await self.jobs_collection.create_index(
                [("createdAt", -1)], name="idx_created_at_desc"
            )
            await self.jobs_collection.create_index(
                [("username", 1), ("status", 1), ("createdAt", -1)],
                name="idx_user_status_created",
            )

            self.logger.info("MongoDB indexes created successfully")

        except Exception as e:
            self.logger.error(f"Failed to create indexes: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if MongoDB is accessible and responsive."""
        try:
            if not self.client:
                return False
            await self.client.admin.command("ping")
            return True
        except Exception as e:
            self.logger.error(f"MongoDB health check failed: {e}")
            return False

    def _job_to_document(self, job: Job) -> dict:
        """Convert Job model to MongoDB document format."""
        doc = job.model_dump()
        # map mongo's _id to our schema's id
        doc["_id"] = job.id
        if "id" in doc:
            del doc["id"]
        return doc

    def _document_to_job(self, doc: dict) -> Job:
        """Convert MongoDB document to Job model."""
        # map mongo's _id to our schema's id
        if "_id" in doc:
            doc["id"] = doc["_id"]
            del doc["_id"]
        return Job(**doc)

    async def create_job(self, job_data: JobCreate) -> Job:
        """Create a new job in MongoDB."""
        attempts = 0
        while attempts < self.ID_GENERATION_MAX_RETRIES:
            try:
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
                await self.jobs_collection.insert_one(self._job_to_document(job))
                return job
            except DuplicateKeyError:
                attempts += 1
                continue
            except Exception as e:
                self.logger.error(f"Failed to create job: {e}")
                raise
        raise RuntimeError(
            f"Failed to generate unique job ID after {self.ID_GENERATION_MAX_RETRIES} attempts"
        )

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by its ID from MongoDB."""
        try:
            doc = await self.jobs_collection.find_one({"_id": job_id})
            if doc:
                return self._document_to_job(doc)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get job {job_id}: {e}")
            raise

    async def list_jobs(self, filters: JobFilters) -> Tuple[List[Job], int]:
        """List jobs with filtering and pagination using MongoDB queries."""
        try:
            query = {}
            if filters.username:
                query["username"] = filters.username
            if filters.jobName:
                query["jobName"] = filters.jobName
            if filters.status:
                query["status"] = filters.status.value

            total_count = await self.jobs_collection.count_documents(query)

            pipeline = [
                {"$match": query},
                {"$sort": {"createdAt": -1}},  # Most recent first
            ]

            # Add pagination
            limit, offset = filters.get_pagination()
            if offset > 0:
                pipeline.append({"$skip": offset})
            if limit is not None:
                pipeline.append({"$limit": limit})

            # Execute query
            cursor = self.jobs_collection.aggregate(pipeline)
            docs = await cursor.to_list(length=None)

            # Convert documents to Job objects
            jobs = [self._document_to_job(doc) for doc in docs]

            return jobs, total_count

        except Exception as e:
            self.logger.error(f"Failed to list jobs: {e}")
            raise

    async def update_job(self, job_id: str, updates: dict) -> Optional[Job]:
        """Update specific fields of a job in MongoDB."""
        try:
            # Add updatedAt timestamp to updates
            updates_with_timestamp = {
                **updates,
                "updatedAt": datetime.now(timezone.utc),
            }

            # Perform atomic update
            result = await self.jobs_collection.find_one_and_update(
                {"_id": job_id},
                {"$set": updates_with_timestamp},
                return_document=ReturnDocument.AFTER,
            )

            if result:
                return self._document_to_job(result)
            return None

        except Exception as e:
            self.logger.error(f"Failed to update job {job_id}: {e}")
            raise

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job by its ID from MongoDB."""
        try:
            result = await self.jobs_collection.delete_one({"_id": job_id})
            return result.deleted_count > 0
        except Exception as e:
            self.logger.error(f"Failed to delete job {job_id}: {e}")
            raise

    async def cleanup(self) -> None:
        """Close MongoDB connection and clean up resources."""
        try:
            if self.client:
                self.client.close()
                self.logger.info("MongoDB connection closed")
        except Exception as e:
            self.logger.error(f"Error during MongoDB cleanup: {e}")
