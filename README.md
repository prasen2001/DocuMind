# DocuMind

DocuMind is a local-first PDF analysis workspace. It extracts text, tables, images, layout,
and source coordinates, then answers questions with page-level evidence you can inspect.

## Current milestone

The current usable vertical slice includes:

- safe PDF upload and persistent local document storage;
- native text extraction with words, blocks, reading order, and bounding boxes;
- embedded-image extraction with clipped-render fallback and page rendering;
- native vector-table detection plus OpenCV/Tesseract reconstruction of scanned grid tables;
- lightweight layout labels (title, heading, paragraph, list, header, footer, image);
- optional Tesseract OCR for scanned pages, with confidence and source coordinates;
- OpenCV deskewing, adaptive thresholding, and structural-line diagnostics before OCR;
- deterministic reading-order and caption-to-figure/table relationships;
- vector chart detection with titles, labels, numeric values, and source boxes;
- evidence-grounded lexical question answering with highlighted source regions;
- side-by-side multi-document comparison with isolated evidence per document;
- a responsive document intelligence dashboard with no frontend build step.

OCR is capability-detected. Native-text PDFs work with only Python and PyMuPDF. When the
`tesseract` executable is installed, scanned pages are rendered at high resolution, recognized,
and mapped back to PDF coordinates. Without it, scanned pages remain available for review and
carry an explicit `needs_ocr` status.

Install the reviewed vision extras for OpenCV preprocessing:

```bash
.venv/bin/pip install -e '.[vision]'
```

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/documind
```

Open <http://127.0.0.1:8000>. Data is written under `./data` by default. Override it with
`DOCUMIND_DATA_DIR`, or choose another bind address with `DOCUMIND_HOST` and `DOCUMIND_PORT`.

For the containerized service with Tesseract OCR included:

```bash
docker compose up --build
```

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

## HTTP API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Runtime and extraction capabilities |
| `GET` | `/api/documents` | List ingested documents |
| `POST` | `/api/documents` | Upload raw PDF bytes; filename in `X-Filename` |
| `POST` | `/api/jobs` | Queue asynchronous PDF ingestion |
| `GET` | `/api/jobs/{id}` | Poll ingestion status |
| `GET` | `/api/search?q=...` | Search evidence across all documents |
| `GET` | `/api/metrics` | Pipeline throughput, failures, latency, and queue depth |
| `GET` | `/api/reviews?status=pending` | List evidence awaiting human review |
| `POST` | `/api/reviews/{id}/decision` | Record an approved or rejected review decision |
| `GET` | `/api/documents/{id}` | Full structured extraction result |
| `GET` | `/api/documents/{id}/pages/{n}.png` | Render a page |
| `POST` | `/api/documents/{id}/questions` | Ask a question and receive cited regions |
| `POST` | `/api/compare` | Compare a question across two to ten documents |
| `DELETE` | `/api/documents/{id}` | Delete one local document |

The stored document schema is currently `1.1`. Every page contains normalized regions, tables,
images, charts, and relationships. OCR regions include `source: "tesseract"` and a confidence
score; chart regions use `source: "vector-chart"`.

## Design principles

1. Evidence is data, not decoration. Every extracted element keeps its page and PDF coordinate box.
2. Processing is deterministic before it is clever. More capable models can replace individual
   stages without changing the stored document contract.
3. Local by default. Uploaded files do not leave the machine.
4. Capability gaps are visible. Missing OCR, malformed pages, and partial extraction are reported.

The dashboard uses asynchronous ingestion by default. `DOCUMIND_WORKERS` controls the bounded
worker pool (default `2`). Metrics are process-local in this stage; a production deployment should
export them to durable monitoring before running multiple replicas.

Human-review tasks are created automatically for pages still requiring OCR, extraction warnings,
OCR regions below 75% confidence, and chart regions below 65% confidence. Decisions persist in
`reviews.json` with reviewer, note, and timestamp fields and can be opened directly on the cited
page region from the dashboard.

See [ROADMAP.md](ROADMAP.md) for the staged plan and [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md)
for the dependency-origin and license policy.

