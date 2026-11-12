# Delivery roadmap

The milestones are vertical slices: each one leaves the application runnable and testable.

| Milestone | Deliverable | Status | Acceptance signal |
| --- | --- | --- | --- |
| 1 | Upload PDF and extract text | Complete | Native and optional OCR text retain page and source boxes |
| 2 | Detect and extract tables | Foundation | PyMuPDF table output is normalized; harder cases need CV |
| 3 | Identify document layout | Foundation | Region labels, reading order, and caption relationships |
| 4 | Extract information from charts | Planned | Chart regions, axes, legends, series, and values |
| 5 | Ask questions about documents | Foundation | Local lexical retrieval with abstention |
| 6 | Highlight source regions | Foundation | Answer citations map onto rendered page coordinates |
| 7 | Compare multiple documents | Foundation | Parallel retrieval preserves independent citations |
| 8 | Complete intelligence dashboard | In progress | Ingestion, viewer, evidence, jobs, review, monitoring |

## Phases

### Phase 1 — document processing

Native extraction, rendered page assets, OCR capability detection, Tesseract coordinate mapping,
and regression tests are implemented. Preprocessing profiles and a larger golden corpus remain.

### Phase 2 — computer vision

Use OpenCV for deskew, denoise, adaptive thresholding, contour detection, and bounding-box
normalization. Retain intermediate diagnostics for human review.

### Phase 3 — layout understanding

Strengthen reading order, multi-column segmentation, table reconstruction, captions, and explicit
text–image relationships. Layout models must plug into the existing region contract.

### Phase 4 — multimodal intelligence

Introduce a U.S.-origin, open-source vision-language model only after evaluation on a versioned
document set. Store model-derived claims separately from deterministic extraction.

### Phase 5 — production engineering

Split the local worker from the API, add PostgreSQL-backed metadata, Redis-compatible queues,
vector search, access control, retention policies, tracing, evaluation dashboards, and review jobs.

