import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class DeployConfigIn(BaseModel):
    mode: Literal["auto", "schedule", "paused"]
    interval_minutes: int = Field(default=10, ge=1, le=1440)
    schedule_times: list[str] = Field(default_factory=list, max_length=24)

    @field_validator("schedule_times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        for t in v:
            if not HHMM.match(t):
                raise ValueError("Use HH:MM (24-hour) times, e.g. 02:00")
        return sorted(set(v))


class Version(BaseModel):
    commit: str | None
    subject: str | None
    date: str | None


class ReleaseOut(BaseModel):
    id: int
    commit: str
    pr_number: int | None
    pr_url: str | None  # the pull request on GitHub
    title: str  # the pull request's title
    details: str | None  # a short summary of what it did
    committed_at: datetime | None
    deployed_at: datetime
    storefront_build: str | None
    main_site_build: str | None
    current: bool  # the version running now
    restorable: bool  # an earlier version that can be put back


class DeployStatusOut(BaseModel):
    mode: str
    interval_minutes: int
    schedule_times: list[str]
    timezone: str
    requested_at: datetime | None
    requested_by: str | None
    last_check_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    running: bool
    last_reason: str | None
    last_result: str | None
    updated_at: datetime | None
    updated_by: str | None
    api: Version  # the code the API runs (the server's checkout)
    storefront_build: str | None  # BUILD_SHA of the installed storefront bundle
    main_site_build: str | None  # BUILD_SHA of the installed windycitywares.com bundle
    cron_seen: bool  # the server's cron job has called in within the last few minutes
    last_seen_at: datetime | None
    pinned_commit: str | None  # set while an earlier version is held; newer builds are not installed
    pinned_by: str | None
    pinned_at: datetime | None
    restore_pending: bool  # a restore is waiting for the server's next cron run


class RestoreIn(BaseModel):
    release_id: int


class DeployLogOut(BaseModel):
    log: str


class ReleasesOut(BaseModel):
    releases: list[ReleaseOut]
