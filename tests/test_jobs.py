import time

from documind.jobs import IngestionJobs


class FakeStore:
    def ingest(self, payload: bytes, filename: str) -> dict:
        if not payload.startswith(b"%PDF"):
            raise ValueError("not a PDF")
        return {"id": "document-1", "filename": filename}


def await_terminal(jobs: IngestionJobs, job_id: str) -> dict:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = jobs.get(job_id)
        if job["status"] in {"ready", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


def test_processes_ingestion_asynchronously_and_reports_metrics() -> None:
    jobs = IngestionJobs(FakeStore(), workers=1)  # type: ignore[arg-type]
    try:
        submitted = jobs.submit(b"%PDF-1.7", "report.pdf")
        completed = await_terminal(jobs, submitted["id"])

        assert completed["status"] == "ready"
        assert completed["document_id"] == "document-1"
        assert jobs.metrics()["jobs_completed"] == 1
        assert jobs.metrics()["queue_depth"] == 0
    finally:
        jobs.shutdown()


def test_captures_pipeline_failure_without_losing_job_state() -> None:
    jobs = IngestionJobs(FakeStore(), workers=1)  # type: ignore[arg-type]
    try:
        submitted = jobs.submit(b"not-pdf", "broken.pdf")
        failed = await_terminal(jobs, submitted["id"])

        assert failed["status"] == "failed"
        assert failed["error"] == "not a PDF"
        assert jobs.metrics()["jobs_failed"] == 1
    finally:
        jobs.shutdown()
