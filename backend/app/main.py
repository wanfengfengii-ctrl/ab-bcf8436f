"""FastAPI application: scheduling API plus the built frontend (merged deploy)."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .scheduler import ProblemSpec, TargetSpec, solve
from .schemas import (
    ObjectiveOut,
    Phase,
    ScheduleRequest,
    ScheduleResponse,
    StepOut,
)

app = FastAPI(title="Radio Observation Scheduler", version="1.0.0")

# Same-origin in the merged deployment; permissive CORS only helps local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/schedule", response_model=ScheduleResponse)
def schedule(request: ScheduleRequest) -> ScheduleResponse:
    problem = ProblemSpec(
        initial_time=request.initial.time,
        initial_azimuth=request.initial.azimuth,
        initial_elevation=request.initial.elevation,
        azimuth_speed=request.azimuth_speed,
        elevation_speed=request.elevation_speed,
        targets=[
            TargetSpec(
                id=t.id,
                azimuth=t.azimuth,
                elevation=t.elevation,
                duration=t.duration,
                window_start=t.window_start,
                window_end=t.window_end,
                priority=t.priority,
                mandatory=t.mandatory,
            )
            for t in request.targets
        ],
    )
    solution = solve(problem)
    if not solution.feasible:
        return ScheduleResponse(
            status="infeasible",
            detail="No feasible observation sequence includes all mandatory targets.",
            unselected=solution.unselected,
        )
    return ScheduleResponse(
        status="ok",
        objective=ObjectiveOut(
            total_priority=solution.total_priority,
            target_count=len(solution.steps),
            end_time=solution.end_time if solution.end_time is not None else request.initial.time,
        ),
        steps=[
            StepOut(
                target_id=step.target_id,
                slew=Phase(start=step.slew_start, end=step.slew_end),
                wait=Phase(start=step.wait_start, end=step.wait_end),
                observe=Phase(start=step.observe_start, end=step.observe_end),
            )
            for step in solution.steps
        ],
        unselected=solution.unselected,
    )


def _static_dir() -> str | None:
    env_dir = os.environ.get("STATIC_DIR")
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    # Source checkout layout: <repo>/frontend/dist next to <repo>/backend.
    candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")
    for candidate in candidates:
        if candidate.is_dir():
            return str(candidate)
    return None


_STATIC = _static_dir()
if _STATIC:
    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="frontend")
