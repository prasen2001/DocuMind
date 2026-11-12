from pathlib import Path

import pytest

from documind.reviews import ReviewQueue


def uncertain_document() -> dict:
    return {
        "id": "document-1",
        "filename": "scan.pdf",
        "pages": [
            {
                "number": 1,
                "width": 600,
                "height": 800,
                "needs_ocr": False,
                "warnings": [],
                "regions": [
                    {
                        "id": "ocr-1",
                        "source": "tesseract",
                        "confidence": 61.5,
                        "bbox": [10, 20, 200, 40],
                    }
                ],
                "charts": [
                    {
                        "id": "chart-1",
                        "confidence": 0.58,
                        "bbox": [20, 100, 500, 400],
                    }
                ],
            }
        ],
    }


def test_creates_deduplicated_persistent_review_tasks(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "reviews.json")

    created = queue.create_for_document(uncertain_document())
    duplicate = queue.create_for_document(uncertain_document())

    assert len(created) == 2
    assert duplicate == []
    assert {review["issue_type"] for review in queue.list(status="pending")} == {
        "low-confidence-ocr",
        "low-confidence-chart",
    }


def test_records_auditable_review_decision(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "reviews.json")
    review = queue.create_for_document(uncertain_document())[0]

    decided = queue.decide(
        review["id"], decision="approved", note="Checked against the page", reviewer="analyst"
    )

    assert decided["status"] == "approved"
    assert decided["reviewer"] == "analyst"
    assert decided["decision_note"] == "Checked against the page"
    assert decided["decided_at"]
    assert ReviewQueue(tmp_path / "reviews.json").list(status="approved")[0]["id"] == review["id"]


def test_rejects_invalid_decision(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "reviews.json")
    review = queue.create_for_document(uncertain_document())[0]
    with pytest.raises(ValueError, match="approved or rejected"):
        queue.decide(review["id"], decision="maybe")
