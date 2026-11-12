from pathlib import Path

import pymupdf
import pytest

from documind.storage import DocumentStore


def pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "A locally stored document")
    payload = document.tobytes()
    document.close()
    return payload


def test_ingest_list_get_delete(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path / "data")
    created = store.ingest(pdf_bytes(), "../report.pdf")

    assert created["filename"] == "report.pdf"
    assert store.list()[0]["id"] == created["id"]
    assert store.get(created["id"])["sha256"] == created["sha256"]
    assert store.source_path(created["id"]).is_file()

    store.delete(created["id"])
    assert store.list() == []


def test_rejects_non_pdf(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path / "data")
    with pytest.raises(ValueError, match="not a PDF"):
        store.ingest(b"plain text", "notes.txt")


def test_rejects_path_like_document_ids(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path / "data")
    with pytest.raises(FileNotFoundError):
        store.get("../outside")
