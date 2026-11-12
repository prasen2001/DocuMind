# Dependency policy

DocuMind accepts only dependencies that are open source and meet the project's U.S.-origin rule.
For this repository, “origin” means the project was created by, or is stewarded by, a U.S.-based
organization. Transitive dependencies are reviewed separately before production distribution.

| Component | Role | License | Origin evidence | Decision |
| --- | --- | --- | --- | --- |
| Python | Runtime and standard-library web service | PSF-2.0 | Python Software Foundation, U.S. nonprofit | Allowed |
| PyMuPDF / MuPDF | PDF parsing, extraction, rendering | AGPL-3.0-or-later | Artifex Software, San Francisco, U.S. | Allowed with AGPL obligations |
| Tesseract | Optional OCR engine | Apache-2.0 | Created at HP; later developed at Google | Allowed |
| OpenCV | Optional image preprocessing | Apache-2.0 | Began at Intel Research; U.S. foundation | Allowed |
| NumPy | OpenCV array bridge | BSD-3-Clause | Created in 2005 by U.S.-based project founder Travis Oliphant | Allowed |
| PyTorch | Optional semantic inference | BSD-3-Clause | Created and open-sourced by Meta; Linux Foundation stewardship | Optional |
| Transformers | Optional embedding model runtime | Apache-2.0 | Hugging Face, founded in New York, U.S. | Optional |
| Nomic Embed Text v1.5 | Optional semantic text encoder model | Apache-2.0 | Nomic, founded and headquartered in New York City | Optional model artifact |
| Microsoft Florence-2 | Optional visual captioning and grounding | MIT | Microsoft Research | Optional |

PyMuPDF's AGPL license is important: a deployed network service may need to provide corresponding
source code. Organizations unable to meet those terms must obtain a commercial license or approve
an alternative PDF engine. This is an engineering policy summary, not legal advice.

The initial application avoids frameworks and JavaScript packages. This keeps the dependency
surface auditable while the processing contract stabilizes. PaddleOCR, Qwen, Qdrant, and Docling
are not included because they do not satisfy the current interpretation of the origin constraint.

