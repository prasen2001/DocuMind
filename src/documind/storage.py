from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .extractor import extract_pdf


class DocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def ingest(self, payload: bytes, filename: str) -> dict[str, Any]:
        if not payload.startswith(b"%PDF-"):
            raise ValueError("The uploaded file is not a PDF")
        document_id = uuid.uuid4().hex
        safe_filename = Path(filename).name or "document.pdf"
        if not safe_filename.lower().endswith(".pdf"):
            safe_filename += ".pdf"
        target = self.root / document_id
        target.mkdir(mode=0o700)
        pdf_path = target / "source.pdf"
        try:
            self._atomic_write(pdf_path, payload)
            document = extract_pdf(pdf_path, document_id=document_id, filename=safe_filename)
            self._atomic_json(target / "document.json", document)
            return document
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

    def list(self) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for metadata_path in self.root.glob("*/document.json"):
            try:
                document = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            documents.append(
                {
                    key: document[key]
                    for key in (
                        "id",
                        "filename",
                        "created_at",
                        "status",
                        "size_bytes",
                        "summary",
                        "warnings",
                    )
                }
            )
        return sorted(documents, key=lambda item: item["created_at"], reverse=True)

    def get(self, document_id: str) -> dict[str, Any]:
        path = self._document_dir(document_id) / "document.json"
        if not path.is_file():
            raise FileNotFoundError(document_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def source_path(self, document_id: str) -> Path:
        path = self._document_dir(document_id) / "source.pdf"
        if not path.is_file():
            raise FileNotFoundError(document_id)
        return path

    def delete(self, document_id: str) -> None:
        target = self._document_dir(document_id)
        if not (target / "document.json").is_file():
            raise FileNotFoundError(document_id)
        shutil.rmtree(target)

    def _document_dir(self, document_id: str) -> Path:
        if not document_id or any(char not in "0123456789abcdef" for char in document_id):
            raise FileNotFoundError(document_id)
        target = (self.root / document_id).resolve()
        if target.parent != self.root:
            raise FileNotFoundError(document_id)
        return target

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def _atomic_json(cls, path: Path, value: dict[str, Any]) -> None:
        cls._atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode())
