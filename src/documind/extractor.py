from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf

from .charts import extract_charts
from .ocr import extract_ocr_regions, ocr_available
from .relationships import infer_relationships
from .vision import preprocess_page


def _box(value: Any) -> list[float]:
    """Return a stable, JSON-safe PDF coordinate box."""
    if not value or len(value) != 4:
        return [0.0, 0.0, 0.0, 0.0]
    return [round(float(part), 2) for part in value]


def _region_label(text: str, bbox: list[float], page_height: float, font_size: float) -> str:
    stripped = text.strip()
    y0, y1 = bbox[1], bbox[3]
    if font_size >= 18:
        return "title"
    if y0 < page_height * 0.07:
        return "header"
    if y1 > page_height * 0.93:
        return "footer"
    if re.match(r"^(?:[•●▪◦*-]|\d+[.)])\s+", stripped):
        return "list"
    if font_size >= 13 or (len(stripped) < 90 and stripped.endswith(":")):
        return "heading"
    return "paragraph"


def _extract_tables(page: pymupdf.Page) -> tuple[list[dict[str, Any]], list[str]]:
    tables: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        finder = page.find_tables()
        for index, table in enumerate(finder.tables):
            rows = table.extract()
            tables.append(
                {
                    "id": f"table-{page.number + 1}-{index + 1}",
                    "bbox": _box(table.bbox),
                    "rows": [[cell or "" for cell in row] for row in rows],
                    "row_count": len(rows),
                    "column_count": max((len(row) for row in rows), default=0),
                }
            )
    except Exception as exc:  # noqa: BLE001 - malformed drawings must not abort extraction
        warnings.append(f"Table detection skipped: {type(exc).__name__}")
    return tables, warnings


def extract_pdf(pdf_path: Path, *, document_id: str, filename: str) -> dict[str, Any]:
    """Extract a normalized, evidence-addressable representation from a PDF."""
    file_bytes = pdf_path.read_bytes()
    pages: list[dict[str, Any]] = []
    total_text = 0
    total_images = 0
    total_tables = 0
    total_charts = 0
    ocr_applied_pages = 0
    preprocessed_pages = 0
    document_warnings: list[str] = []

    with pymupdf.open(stream=file_bytes, filetype="pdf") as document:
        if document.needs_pass:
            raise ValueError("Password-protected PDFs are not supported yet")

        for page_index, page in enumerate(document):
            page_dict = page.get_text("dict", sort=True)
            image_info = page.get_image_info(xrefs=True)
            regions: list[dict[str, Any]] = []
            images: list[dict[str, Any]] = []

            for block_index, block in enumerate(page_dict.get("blocks", [])):
                bbox = _box(block.get("bbox"))
                if block.get("type") == 1:
                    block_rect = pymupdf.Rect(bbox)
                    matching_image = min(
                        image_info,
                        key=lambda info: (
                            abs(pymupdf.Rect(info["bbox"]).get_area() - block_rect.get_area())
                            + abs(pymupdf.Rect(info["bbox"]).x0 - block_rect.x0)
                            + abs(pymupdf.Rect(info["bbox"]).y0 - block_rect.y0)
                        ),
                        default={},
                    )
                    images.append(
                        {
                            "id": f"image-{page_index + 1}-{len(images) + 1}",
                            "bbox": bbox,
                            "width": int(block.get("width", 0)),
                            "height": int(block.get("height", 0)),
                            "extension": block.get("ext", "unknown"),
                            "xref": int(matching_image.get("xref", 0)),
                        }
                    )
                    regions.append(
                        {
                            "id": f"region-{page_index + 1}-{block_index + 1}",
                            "type": "image",
                            "bbox": bbox,
                            "text": "",
                            "font_size": 0,
                            "reading_order": len(regions),
                        }
                    )
                    continue
                if block.get("type") != 0:
                    continue

                lines: list[str] = []
                max_font_size = 0.0
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    line_text = "".join(span.get("text", "") for span in spans).strip()
                    if line_text:
                        lines.append(line_text)
                    max_font_size = max(
                        max_font_size,
                        max((float(span.get("size", 0)) for span in spans), default=0),
                    )
                text = "\n".join(lines).strip()
                if not text:
                    continue
                total_text += len(text)
                regions.append(
                    {
                        "id": f"region-{page_index + 1}-{block_index + 1}",
                        "type": _region_label(text, bbox, page.rect.height, max_font_size),
                        "bbox": bbox,
                        "text": text,
                        "font_size": round(max_font_size, 2),
                        "reading_order": len(regions),
                    }
                )

            tables, warnings = _extract_tables(page)
            charts = extract_charts(page, regions)
            total_images += len(images)
            total_tables += len(tables)
            total_charts += len(charts)
            image_area = sum(
                max(0, image["bbox"][2] - image["bbox"][0])
                * max(0, image["bbox"][3] - image["bbox"][1])
                for image in images
            )
            page_area = max(1, page.rect.width * page.rect.height)
            page_text = "\n".join(r["text"] for r in regions if r["text"])
            needs_ocr = len(page_text.strip()) < 20 and image_area / page_area > 0.45
            preprocessing: dict[str, Any] | None = None
            if needs_ocr:
                try:
                    prepared = preprocess_page(page)
                except (RuntimeError, ValueError) as exc:
                    prepared = None
                    warnings.append(f"Image preprocessing failed: {exc}")
                if prepared:
                    preprocessed_pages += 1
                    preprocessing = {
                        key: value for key, value in prepared.items() if key != "image"
                    }
                if ocr_available():
                    try:
                        ocr_regions = extract_ocr_regions(
                            page,
                            scale=prepared["scale"] if prepared else 2.0,
                            image_bytes=prepared["image"] if prepared else None,
                        )
                        for ocr_region in ocr_regions:
                            ocr_region["id"] = f"region-{page_index + 1}-ocr-{len(regions) + 1}"
                            ocr_region["reading_order"] = len(regions)
                            regions.append(ocr_region)
                        if ocr_regions:
                            ocr_applied_pages += 1
                            recognized = "\n".join(region["text"] for region in ocr_regions)
                            page_text = recognized
                            total_text += len(recognized)
                            needs_ocr = False
                        else:
                            warnings.append("Tesseract found no text on this scanned page")
                    except (RuntimeError, OSError, TimeoutError) as exc:
                        warnings.append(f"OCR failed: {exc}")
                else:
                    warnings.append("Page appears scanned; install Tesseract to enable OCR")
            relationships = infer_relationships(page_index + 1, regions, images, tables, charts)
            for chart in charts:
                chart_text = " ".join(
                    part for part in [chart["title"], *chart["labels"]] if part
                ).strip()
                if chart_text:
                    regions.append(
                        {
                            "id": f"region-{page_index + 1}-chart-{len(regions) + 1}",
                            "type": "chart",
                            "bbox": chart["bbox"],
                            "text": chart_text,
                            "font_size": 0,
                            "reading_order": len(regions),
                            "source": "vector-chart",
                            "chart_id": chart["id"],
                        }
                    )
            pages.append(
                {
                    "number": page_index + 1,
                    "width": round(page.rect.width, 2),
                    "height": round(page.rect.height, 2),
                    "rotation": page.rotation,
                    "text": page_text,
                    "regions": regions,
                    "images": images,
                    "tables": tables,
                    "charts": charts,
                    "relationships": relationships,
                    "needs_ocr": needs_ocr,
                    "ocr_applied": any(region.get("source") == "tesseract" for region in regions),
                    "preprocessing": preprocessing,
                    "warnings": warnings,
                }
            )

        metadata = {key: value or "" for key, value in document.metadata.items()}

    if not total_text:
        document_warnings.append("No machine-readable text was found")
    return {
        "schema_version": "1.1",
        "id": document_id,
        "filename": filename,
        "sha256": hashlib.sha256(file_bytes).hexdigest(),
        "size_bytes": len(file_bytes),
        "created_at": datetime.now(UTC).isoformat(),
        "status": "ready",
        "metadata": metadata,
        "summary": {
            "page_count": len(pages),
            "character_count": total_text,
            "image_count": total_images,
            "table_count": total_tables,
            "chart_count": total_charts,
            "ocr_pages": ocr_applied_pages,
            "ocr_required_pages": sum(page["needs_ocr"] for page in pages),
            "preprocessed_pages": preprocessed_pages,
            "relationship_count": sum(len(page["relationships"]) for page in pages),
        },
        "warnings": document_warnings,
        "pages": pages,
    }
