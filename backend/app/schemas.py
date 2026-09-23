"""Request/response schemas for the scheduling API.

All times are integer seconds within the day (0..86399).  Validation errors
are returned as HTTP 422 with Pydantic's ``loc`` field so the client can
pinpoint the offending field.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_SECOND_OF_DAY = 86399


class InitialState(BaseModel):
    """Telescope state at the beginning of the night."""

    time: int = Field(..., ge=0, le=MAX_SECOND_OF_DAY, description="start time, seconds of day")
    azimuth: int = Field(..., ge=0, le=359, description="initial azimuth, degrees")
    elevation: int = Field(..., ge=0, le=90, description="initial elevation, degrees")


class TargetIn(BaseModel):
    id: str = Field(..., min_length=1, max_length=64, description="unique target id")
    azimuth: int = Field(..., ge=0, le=359, description="azimuth, integer degrees")
    elevation: int = Field(..., ge=0, le=90, description="elevation, integer degrees")
    duration: int = Field(..., gt=0, le=86400, description="observation duration, seconds")
    window_start: int = Field(..., ge=0, le=MAX_SECOND_OF_DAY, description="visibility window start, seconds of day")
    window_end: int = Field(..., ge=0, le=MAX_SECOND_OF_DAY, description="visibility window end, seconds of day")
    priority: int = Field(..., gt=0, description="positive integer priority")
    mandatory: bool = Field(False, description="must be included in the plan")

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("id must not be blank")
        return value

    @model_validator(mode="after")
    def _window_order(self) -> "TargetIn":
        if self.window_end < self.window_start:
            raise ValueError("window_end must be greater than or equal to window_start")
        return self


class ScheduleRequest(BaseModel):
    initial: InitialState
    azimuth_speed: float = Field(..., gt=0, le=360, description="azimuth slew speed, degrees/second")
    elevation_speed: float = Field(..., gt=0, le=360, description="elevation slew speed, degrees/second")
    targets: List[TargetIn] = Field(..., min_length=2, max_length=16)

    @model_validator(mode="after")
    def _unique_ids(self) -> "ScheduleRequest":
        seen: set[str] = set()
        duplicates: list[str] = []
        for target in self.targets:
            if target.id in seen and target.id not in duplicates:
                duplicates.append(target.id)
            seen.add(target.id)
        if duplicates:
            raise ValueError("duplicate target id(s): " + ", ".join(sorted(duplicates)))
        return self


class Phase(BaseModel):
    start: int
    end: int


class StepOut(BaseModel):
    target_id: str
    slew: Phase = Field(..., description="slew towards the target (zero-length if already aligned)")
    wait: Phase = Field(..., description="waiting for the window to open (zero-length if none)")
    observe: Phase = Field(..., description="observation interval, always inside the window")


class ObjectiveOut(BaseModel):
    total_priority: int
    target_count: int
    end_time: int = Field(..., description="end of the last observation, seconds of day")


class ScheduleResponse(BaseModel):
    status: str = Field(..., description="'ok' or 'infeasible'")
    detail: Optional[str] = None
    objective: Optional[ObjectiveOut] = None
    steps: Optional[List[StepOut]] = None
    unselected: Optional[List[str]] = None
