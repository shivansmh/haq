from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4


@dataclass
class SweepJob:
    job_id: str
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    state: str = "queued"
    listed: int = 0
    triaged: int = 0
    analysed: int = 0
    relevant: int = 0
    not_analysed: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None
    thread: threading.Thread | None = field(default=None, repr=False)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        return {
            "job_id": self.job_id,
            "state": self.state,
            "listed": self.listed,
            "triaged": self.triaged,
            "analysed": self.analysed,
            "relevant": self.relevant,
            "not_analysed": self.not_analysed,
            "elapsed_seconds": round(max(0.0, now - self.created_at), 3),
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "error": self.error,
            "result": self.result,
        }


class SweepJobManager:
    def __init__(self, *, ttl_seconds: int | None = None) -> None:
        self.ttl_seconds = ttl_seconds or int(os.getenv("SWEEP_JOB_TTL_SECONDS", "3600"))
        self._jobs: dict[str, SweepJob] = {}
        self._lock = threading.RLock()

    def _clean(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        for job_id, job in list(self._jobs.items()):
            if job.updated_at < cutoff and job.state in {"done", "failed", "expired", "cancelled"}:
                self._jobs.pop(job_id, None)

    def start(self, session_id: str, worker: Callable[[SweepJob], dict[str, Any]]) -> SweepJob:
        with self._lock:
            self._clean()
            for existing in self._jobs.values():
                if existing.session_id == session_id and existing.state in {"queued", "running", "cancelling"}:
                    raise ValueError("a sweep is already running for this session")
            job = SweepJob(uuid4().hex, session_id)
            self._jobs[job.job_id] = job
            job.thread = threading.Thread(target=self._run, args=(job, worker), daemon=True)
            job.thread.start()
            return job

    def _run(self, job: SweepJob, worker: Callable[[SweepJob], dict[str, Any]]) -> None:
        with self._lock:
            job.state = "running"
            job.updated_at = time.time()
        try:
            result = worker(job)
            with self._lock:
                if job.cancel_event.is_set():
                    job.state = "expired" if job.state == "expired" else "cancelled"
                else:
                    job.result = result
                    job.state = "done"
                job.updated_at = time.time()
        except Exception as exc:
            with self._lock:
                job.error = type(exc).__name__
                job.state = "failed"
                job.updated_at = time.time()

    def get(self, job_id: str, session_id: str) -> SweepJob | None:
        with self._lock:
            self._clean()
            job = self._jobs.get(job_id)
            if not job or job.session_id != session_id:
                return None
            if time.time() - job.created_at > self.ttl_seconds and job.state not in {"done", "failed", "cancelled"}:
                job.state = "expired"
                job.cancel_event.set()
                job.updated_at = time.time()
            return job

    def cancel(self, job_id: str, session_id: str) -> SweepJob | None:
        job = self.get(job_id, session_id)
        if job and job.state in {"queued", "running"}:
            job.state = "cancelling"
            job.cancel_event.set()
            job.updated_at = time.time()
        return job


SWEEP_JOBS = SweepJobManager()
