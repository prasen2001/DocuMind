# Delivery roadmap

The milestones are vertical slices: each one leaves the application runnable and testable.

| Milestone | Deliverable | Status | Acceptance signal |
| --- | --- | --- | --- |
| 1 | Upload PDF and extract text | Complete | Native and optional OCR text retain page and source boxes |
| 2 | Detect and extract tables | Foundation | Native vector and scanned OCR grid tables are normalized |
| 3 | Identify document layout | Foundation | Region labels, reading order, and caption relationships |
| 4 | Extract information from charts | Foundation | Vector chart regions, labels, values, and evidence boxes |
| 5 | Ask questions about documents | Foundation | Local lexical retrieval with abstention |
| 6 | Highlight source regions | Foundation | Answer citations map onto rendered page coordinates |
| 7 | Compare multiple documents | Foundation | Parallel retrieval preserves independent citations |
| 8 | Complete intelligence dashboard | In progress | Async ingestion, search, evidence, review, comparison, metrics |

## Phases

### Phase 1 — document processing

Native extraction, rendered page assets, OCR capability detection, Tesseract coordinate mapping,
and regression tests are implemented. Preprocessing profiles and a larger golden corpus remain.

### Phase 2 — computer vision

OpenCV deskew, adaptive thresholding, line morphology, contour detection, and PDF-coordinate
normalization are implemented for scanned pages. Diagnostics are retained alongside each page,
and detected grid lines reconstruct OCR words into table cells. Denoising profiles and borderless
table reconstruction remain.

### Phase 3 — layout understanding

Strengthen reading order, multi-column segmentation, table reconstruction, captions, and explicit
text–image relationships. Layout models must plug into the existing region contract.

### Phase 4 — multimodal intelligence

An optional Microsoft Florence-2 adapter now supports image captioning, object detection, dense
region captions, and PDF-coordinate grounding. It is disabled by default; model-derived claims
remain separate from deterministic extraction and are explicitly marked for source review. A
versioned multimodal evaluation set remains before enabling it by default.

### Phase 5 — production engineering

The local service now has a bounded asynchronous ingestion queue, lexical region search, optional
MiniLM contextual vector search,
pipeline metrics, and a container with health checking. Splitting workers from the API,
PostgreSQL-backed metadata, a durable U.S.-origin queue, access control, retention policies,
tracing and evaluation dashboards remain. Persistent local review jobs and auditable decisions
are implemented; a distributed deployment should move them into transactional storage.

