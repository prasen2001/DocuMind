from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ReviewQueue:
    """Persistent human-review queue for uncertain extraction evidence."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create_for_document(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for page in document.get("pages", []):
            if page.get("needs_ocr"):
                candidates.append(
                    self._candidate(
                        document,
                        page,
                        "ocr-required",
                        "high",
                        [0, 0, page["width"], page["height"]],
                    )
                )
            for warning in page.get("warnings", []):
                candidates.append(
                    self._candidate(
                        document,
                        page,
                        "page-warning",
                        "medium",
                        [0, 0, page["width"], page["height"]],
                        detail=warning,
                    )
                )
            for region in page.get("regions", []):
                if region.get("source") == "tesseract" and region.get("confidence", 100) < 75:
                    candidates.append(
                        self._candidate(
                            document,
                            page,
                            "low-confidence-ocr",
                            "high",
                            region["bbox"],
                            region_id=region["id"],
                            detail=f"OCR confidence {region['confidence']}%",
                        )
                    )
            for chart in page.get("charts", []):
                if chart.get("confidence", 1) < 0.65:
                    candidates.append(
                        self._candidate(
                            document,
                            page,
                            "low-confidence-chart",
                            "medium",
                            chart["bbox"],
                            region_id=chart["id"],
                            detail=f"Chart confidence {round(chart['confidence'] * 100)}%",
                        )
                    )

        if not candidates:
            return []
        with self._lock:
            reviews = self._read()
            existing_keys = {review["deduplication_key"] for review in reviews}
            created = []
            for candidate in candidates:
                if candidate["deduplication_key"] in existing_keys:
                    continue
                reviews.append(candidate)
                existing_keys.add(candidate["deduplication_key"])
                created.append(dict(candidate))
            if created:
                self._write(reviews)
            return created

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            reviews = self._read()
        if status:
            reviews = [review for review in reviews if review["status"] == status]
        priority = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            reviews, key=lambda review: (priority.get(review["priority"], 3), review["created_at"])
        )

    def decide(
        self, review_id: str, *, decision: str, note: str = "", reviewer: str = "local-user"
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        with self._lock:
            reviews = self._read()
            for review in reviews:
                if review["id"] == review_id:
                    review.update(
                        status=decision,
                        decision_note=note.strip(),
                        reviewer=reviewer.strip() or "local-user",
                        decided_at=_now(),
                        updated_at=_now(),
                    )
                    self._write(reviews)
                    return dict(review)
        raise FileNotFoundError(review_id)

    @staticmethod
    def _candidate(
        document: dict[str, Any],
        page: dict[str, Any],
        issue_type: str,
        priority: str,
        bbox: list[float],
        *,
        region_id: str | None = None,
        detail: str = "",
    ) -> dict[str, Any]:
        key = f"{document['id']}:{page['number']}:{issue_type}:{region_id or '-'}:{detail}"
        timestamp = _now()
        return {
            "id": uuid.uuid4().hex,
            "deduplication_key": key,
            "document_id": document["id"],
            "filename": document["filename"],
            "page": page["number"],
            "region_id": region_id,
            "bbox": bbox,
            "issue_type": issue_type,
            "detail": detail,
            "priority": priority,
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp,
            "reviewer": None,
            "decision_note": "",
            "decided_at": None,
        }

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    def _write(self, value: list[dict[str, Any]]) -> None:
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".reviews-")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
