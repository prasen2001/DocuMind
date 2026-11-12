from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from .storage import DocumentStore


def _now() -> str:
    return datetime.now(UTC).isoformat()


class IngestionJobs:
    """Bounded in-process ingestion queue with observable job and metric state."""

    def __init__(self, store: DocumentStore, *, workers: int = 2) -> None:
        self.store = store
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, workers), thread_name_prefix="ingest"
        )
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._metrics: dict[str, float] = {
            "jobs_submitted": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "processing_milliseconds": 0,
        }

    def submit(self, payload: bytes, filename: str) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "filename": filename,
            "status": "queued",
            "created_at": _now(),
            "updated_at": _now(),
            "document_id": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._metrics["jobs_submitted"] += 1
        self._executor.submit(self._process, job_id, payload, filename)
        return dict(job)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise FileNotFoundError(job_id)
            return dict(self._jobs[job_id])

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(job) for job in reversed(self._jobs.values())]

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            terminal = self._metrics["jobs_completed"] + self._metrics["jobs_failed"]
            average = self._metrics["processing_milliseconds"] / terminal if terminal else 0
            return {
                **self._metrics,
                "average_processing_milliseconds": round(average, 2),
                "queue_depth": sum(
                    job["status"] in {"queued", "processing"} for job in self._jobs.values()
                ),
            }

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _process(self, job_id: str, payload: bytes, filename: str) -> None:
        started = time.perf_counter()
        self._update(job_id, status="processing")
        try:
            document = self.store.ingest(payload, filename)
        except Exception as exc:  # noqa: BLE001 - job failures are captured as state
            elapsed = (time.perf_counter() - started) * 1000
            with self._lock:
                self._jobs[job_id].update(status="failed", error=str(exc), updated_at=_now())
                self._metrics["jobs_failed"] += 1
                self._metrics["processing_milliseconds"] += elapsed
            return
        elapsed = (time.perf_counter() - started) * 1000
        with self._lock:
            self._jobs[job_id].update(status="ready", document_id=document["id"], updated_at=_now())
            self._metrics["jobs_completed"] += 1
            self._metrics["processing_milliseconds"] += elapsed

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(**values, updated_at=_now())
