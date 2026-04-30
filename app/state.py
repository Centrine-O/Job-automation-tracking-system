"""Shared mutable state: pipeline stage tracker and cached health results.

Both scheduler.py and dashboard/main.py import from here, avoiding circular
imports between those two modules.
"""
from threading import Lock

_lock = Lock()

pipeline: dict = {
    "stage": "idle",
    "last_stage": None,
    "last_run_at": None,
    "stage_started_at": None,
    "error": None,
}

health_cache: dict = {
    "checked_at": None,
    "services": {},
}


def set_stage(stage: str, started_at: str | None = None):
    with _lock:
        pipeline["stage"] = stage
        if started_at:
            pipeline["stage_started_at"] = started_at


def complete_stage(last_stage: str, completed_at: str):
    with _lock:
        pipeline["stage"] = "idle"
        pipeline["last_stage"] = last_stage
        pipeline["last_run_at"] = completed_at
        pipeline["stage_started_at"] = None


def set_error(msg: str | None):
    with _lock:
        pipeline["error"] = msg


def snapshot() -> dict:
    with _lock:
        return dict(pipeline)
