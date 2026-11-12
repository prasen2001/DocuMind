from __future__ import annotations

import json
import logging
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pymupdf

from . import __version__
from .compare import compare_documents
from .jobs import IngestionJobs
from .ocr import ocr_available
from .qa import answer_question
from .reviews import ReviewQueue
from .search import search_documents
from .storage import DocumentStore

LOGGER = logging.getLogger("documind")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class DocuMindServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], store: DocumentStore) -> None:
        super().__init__(address, DocuMindHandler)
        self.store = store
        self.reviews = ReviewQueue(store.root / "reviews.json")
        self.jobs = IngestionJobs(
            store,
            workers=int(os.environ.get("DOCUMIND_WORKERS", "2")),
            on_complete=self.reviews.create_for_document,
        )

    def server_close(self) -> None:
        self.jobs.shutdown()
        super().server_close()


class DocuMindHandler(BaseHTTPRequestHandler):
    server: DocuMindServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/health":
                self._json(
                    {
                        "status": "ok",
                        "version": __version__,
                        "capabilities": {
                            "native_text": True,
                            "tables": True,
                            "layout": True,
                            "page_rendering": True,
                            "ocr": ocr_available(),
                            "question_answering": "lexical",
                        },
                    }
                )
            elif path == "/api/documents":
                self._json({"documents": self.server.store.list()})
            elif path == "/api/jobs":
                self._json({"jobs": self.server.jobs.list()})
            elif path.startswith("/api/jobs/"):
                parts = self._parts(path)
                if len(parts) != 3:
                    raise FileNotFoundError(path)
                self._json(self.server.jobs.get(parts[2]))
            elif path == "/api/search":
                query = parse_qs(parsed.query).get("q", [""])[0].strip()
                limit = int(parse_qs(parsed.query).get("limit", ["20"])[0])
                documents = [self.server.store.get(item["id"]) for item in self.server.store.list()]
                self._json(search_documents(documents, query, limit=limit))
            elif path == "/api/metrics":
                self._json(
                    {
                        **self.server.jobs.metrics(),
                        "document_count": len(self.server.store.list()),
                    }
                )
            elif path == "/api/reviews":
                status = parse_qs(parsed.query).get("status", [None])[0]
                self._json({"reviews": self.server.reviews.list(status=status)})
            elif path.startswith("/api/documents/"):
                self._get_document_route(path)
            else:
                self._static(path)
        except FileNotFoundError:
            self._error(HTTPStatus.NOT_FOUND, "Resource not found")
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception:
            LOGGER.exception("Unhandled GET request")
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "The request could not be completed")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        parts = self._parts(path)
        try:
            if path == "/api/documents":
                payload = self._body(MAX_UPLOAD_BYTES)
                filename = unquote(self.headers.get("X-Filename", "document.pdf"))
                document = self.server.store.ingest(payload, filename)
                self.server.reviews.create_for_document(document)
                self._json(document, HTTPStatus.CREATED)
                return
            if path == "/api/jobs":
                payload = self._body(MAX_UPLOAD_BYTES)
                filename = unquote(self.headers.get("X-Filename", "document.pdf"))
                self._json(self.server.jobs.submit(payload, filename), HTTPStatus.ACCEPTED)
                return
            if path == "/api/compare":
                request = json.loads(self._body(128 * 1024))
                document_ids = request.get("document_ids", [])
                if not isinstance(document_ids, list):
                    raise ValueError("document_ids must be a list")
                documents = [
                    self.server.store.get(str(document_id)) for document_id in document_ids
                ]
                self._json(compare_documents(documents, str(request.get("question", ""))))
                return
            if len(parts) == 4 and parts[:2] == ["api", "reviews"] and parts[3] == "decision":
                request = json.loads(self._body(64 * 1024))
                review = self.server.reviews.decide(
                    parts[2],
                    decision=str(request.get("decision", "")),
                    note=str(request.get("note", "")),
                    reviewer=str(request.get("reviewer", "local-user")),
                )
                self._json(review)
                return
            if len(parts) == 4 and parts[:2] == ["api", "documents"] and parts[3] == "questions":
                request = json.loads(self._body(64 * 1024))
                question = str(request.get("question", "")).strip()
                if not question:
                    raise ValueError("A question is required")
                document = self.server.store.get(parts[2])
                self._json(answer_question(document, question))
                return
            self._error(HTTPStatus.NOT_FOUND, "Route not found")
        except (ValueError, json.JSONDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError:
            self._error(HTTPStatus.NOT_FOUND, "Document not found")
        except pymupdf.FileDataError:
            self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "The PDF is damaged or unsupported")
        except Exception:
            LOGGER.exception("Unhandled POST request")
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "The request could not be completed")

    def do_DELETE(self) -> None:
        parts = self._parts(urlparse(self.path).path)
        try:
            if len(parts) == 3 and parts[:2] == ["api", "documents"]:
                self.server.store.delete(parts[2])
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            self._error(HTTPStatus.NOT_FOUND, "Route not found")
        except FileNotFoundError:
            self._error(HTTPStatus.NOT_FOUND, "Document not found")

    def _get_document_route(self, path: str) -> None:
        parts = self._parts(path)
        if len(parts) == 3:
            self._json(self.server.store.get(parts[2]))
            return
        if len(parts) == 5 and parts[3] == "pages" and parts[4].endswith(".png"):
            page_number = int(parts[4][:-4])
            self._render_page(parts[2], page_number)
            return
        raise FileNotFoundError(path)

    def _render_page(self, document_id: str, page_number: int) -> None:
        source = self.server.store.source_path(document_id)
        with pymupdf.open(source) as document:
            if page_number < 1 or page_number > document.page_count:
                raise FileNotFoundError(page_number)
            page = document[page_number - 1]
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            payload = pixmap.tobytes("png")
        self._bytes(payload, "image/png", cache="private, max-age=3600")

    def _static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        if relative not in {"index.html", "app.js", "styles.css"}:
            raise FileNotFoundError(relative)
        resource = files("documind.web").joinpath(relative)
        content_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"
        self._bytes(resource.read_bytes(), content_type, cache="no-cache")

    def _body(self, maximum: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length <= 0:
            raise ValueError("The request body is empty")
        if length > maximum:
            raise ValueError(f"Request exceeds the {maximum // (1024 * 1024)} MB limit")
        payload = self.rfile.read(length)
        if len(payload) != length:
            raise ValueError("The upload ended unexpectedly")
        return payload

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message, "status": status.value}, status)

    def _bytes(self, payload: bytes, content_type: str, *, cache: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def _parts(path: str) -> list[str]:
        return [part for part in path.split("/") if part]

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    host = os.environ.get("DOCUMIND_HOST", "127.0.0.1")
    port = int(os.environ.get("DOCUMIND_PORT", "8000"))
    data_dir = Path(os.environ.get("DOCUMIND_DATA_DIR", "data"))
    server = DocuMindServer((host, port), DocumentStore(data_dir))
    LOGGER.info("DocuMind %s listening on http://%s:%s", __version__, host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping DocuMind")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
