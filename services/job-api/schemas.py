from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Any, Optional
from enum import Enum


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobCreate(BaseModel):
    """Payload used to create a new job via POST /jobs."""

    jobName: str = Field(min_length=1, max_length=100, description="Job name")
    username: Optional[str] = Field(
        default=None, max_length=50, description="Optional username"
    )
    modelId: str = Field(min_length=1, description="Identifier of the model to run")
    input: Any = Field(description="Input payload for the model")

    @field_validator("jobName")
    @classmethod
    def validate_job_name(cls, v):
        if not v or v.strip() == "":
            raise ValueError("jobName cannot be empty or whitespace only")
        return v.strip()

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if v is not None and v.strip() == "":
            raise ValueError("username cannot be empty or whitespace only")
        return v.strip() if v else None


class Job(BaseModel):
    """
    Represents a job as returned by the API.
    """

    id: str = Field(description="Unique job identifier (UUID)")
    jobName: str = Field(description="Job name")
    username: Optional[str] = Field(default=None, description="Optional username")
    modelId: str = Field(description="Identifier of the model to run")
    input: Any = Field(description="Input payload for the model")
    status: JobStatus = Field(description="Job status")
    result: Optional[Any] = Field(default=None, description="Result once finished")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    createdAt: datetime
    updatedAt: datetime

    model_config = {
        "use_enum_values": True,
        "json_schema_extra": {
            "example": {
                "id": "2d0e1a60-6c0c-4d25-8cb7-1d7e8f6b2b54",
                "jobName": "sentiment-analysis",
                "username": "alice",
                "modelId": "distilbert-base-uncased-finetuned-sst-2-english",
                "input": {"text": "I love this!"},
                "status": "queued",
                "result": None,
                "error": None,
                "createdAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-01-01T00:00:00Z",
            },
        },
    }


class JobFilters(BaseModel):
    """
    Query parameters for listing jobs.
    """

    username: Optional[str] = Field(default=None, description="Filter by username")
    jobName: Optional[str] = Field(default=None, description="Filter by job name")
    status: Optional[JobStatus] = Field(
        default=None, description="Filter by job status"
    )

    # Page-based pagination (preferred for UIs)
    page: Optional[int] = Field(default=None, ge=1, description="Page number (1-based)")
    pageSize: Optional[int] = Field(
        default=None, ge=1, le=100, description="Items per page"
    )

    # Offset-based pagination (preferred for APIs)
    limit: Optional[int] = Field(
        default=None,
        ge=-1,
        le=100,
        description="Maximum number of items to return. Use -1 for unlimited.",
    )
    offset: Optional[int] = Field(
        default=None, ge=0, description="Number of items to skip"
    )

    def get_pagination(self) -> tuple[int | None, int]:
        """
        Convert pagination parameters to (limit, offset).
        Returns default values if no pagination specified.
        Validates that only one pagination approach is used.
        """
        default_limit, default_offset = 20, 0
        page_params = [self.page, self.pageSize]
        offset_params = [self.limit, self.offset]

        page_provided = any(p is not None for p in page_params)
        offset_provided = any(p is not None for p in offset_params)

        if page_provided and offset_provided:
            raise ValueError(
                "Cannot use both page/pageSize and limit/offset pagination"
            )

        if page_provided:
            page = self.page or 1
            page_size = self.pageSize or default_limit
            return page_size, (page - 1) * page_size

        elif offset_provided:
            limit = self.limit
            offset = self.offset or default_offset
            if limit == -1:
                return None, offset
            elif limit is None:
                return default_limit, offset
            return limit, offset
        else:
            return default_limit, default_offset


class PaginatedJobsResponse(BaseModel):
    """
    Response wrapper for paginated job listings.
    """

    jobs: list[Job]
    total: int = Field(description="Total number of jobs matching filters")
    limit: int = Field(description="Number of items per page")
    offset: int = Field(description="Number of items skipped")
    hasMore: bool = Field(description="Whether there are more items available")


__all__ = ["Job", "JobStatus", "JobCreate", "JobFilters"]
