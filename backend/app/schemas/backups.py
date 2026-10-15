"""Database backups (admin)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BackupConfigIn(BaseModel):
    enabled: bool
    hour: int = Field(ge=0, le=23)
    keep: int = Field(ge=1, le=30)
    repo: str | None = Field(default=None, max_length=200)
    branch: str = Field(default="main", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._/-]+$")


class BackupRunOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    status: Literal["running", "success", "failed"]
    trigger: Literal["schedule", "manual"]
    actor_email: str | None
    file_name: str | None
    size_bytes: int | None
    error: str | None


class BackupFileOut(BaseModel):
    name: str
    size: int | None


class BackupsOut(BaseModel):
    enabled: bool
    hour: int
    keep: int
    repo: str | None
    branch: str
    updated_at: datetime | None
    updated_by_email: str | None
    secrets: dict[str, bool]
    runs: list[BackupRunOut]
    files: list[BackupFileOut] | None  # None when the repository couldn't be read
    files_error: str | None = None


class BackupResultOut(BaseModel):
    status: Literal["success", "failed"]
    file_name: str
    size_bytes: int | None = None
    error: str | None = None
    kept: list[str] | None = None
