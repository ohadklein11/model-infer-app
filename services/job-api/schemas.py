from __future__ import annotations

from pydantic import BaseModel, Field
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
	jobName: str = Field(description="Job name")
	username: Optional[str] = Field(default=None, description="Optional username")
	modelId: str = Field(description="Identifier of the model to run")
	input: Any = Field(description="Input payload for the model")




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
		}
	}


class JobFilters(BaseModel):
	"""
	Query parameters for listing jobs.
	"""
	q: Optional[str] = Field(default=None, description="Free text search over name and username")
	username: Optional[str] = Field(default=None, description="Filter by username")
	jobName: Optional[str] = Field(default=None, description="Filter by job name")
	status: Optional[JobStatus] = Field(default=None, description="Filter by job status")
	page: int = Field(default=1, ge=1, description="Page number (1-based)")
	pageSize: int = Field(default=20, ge=1, le=100, description="Items per page")


__all__ = ["Job", "JobStatus", "JobCreate", "JobFilters"]

