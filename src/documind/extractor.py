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
from .tables import extract_ocr_tables
from .vision import preprocess_page

DATE_RANGE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\s*"
    r"(?:[-–—]|\bto\b)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"[a-z]*\.?\s+\d{4}|Present|Current|Now)\b",
    re.IGNORECASE,
)
LIST_MARKER_RE = re.compile(r"^(?:[•●▪◦*–—-]|\d+[.)])\s+")


def _box(value: Any) -> list[float]:
    """Return a stable, JSON-safe PDF coordinate box."""
    if not value or len(value) != 4:
        return [0.0, 0.0, 0.0, 0.0]
    return [round(float(part), 2) for part in value]


def _region_label(
    text: str, bbox: list[float], page_height: float, font_size: float, *, bold: bool = False
) -> str:
    stripped = text.strip()
    y0, y1 = bbox[1], bbox[3]
    if font_size >= 18:
        return "title"
    if y0 < page_height * 0.07:
        return "header"
    if LIST_MARKER_RE.match(stripped):
        return "list"
    if y1 > page_height * 0.93:
        return "footer"
    if (font_size >= 13 or (font_size >= 11.5 and bold)) and len(stripped) < 100:
        return "heading"
    return "paragraph"


def _extract_text_regions(
    page_dict: dict[str, Any], page_index: int, page_height: float
) -> list[dict[str, Any]]:
    """Reconstruct logical paragraphs from positioned PDF lines, not renderer blocks."""
    rows: list[dict[str, Any]] = []
    for block_index, block in enumerate(page_dict.get("blocks", [])):
        if block.get("type") != 0:
            continue
        block_rows: list[list[dict[str, Any]]] = []
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            item = {
                "text": text,
                "bbox": _box(line.get("bbox")),
                "font_size": max((float(span.get("size", 0)) for span in spans), default=0),
                "bold": any(int(span.get("flags", 0)) & 16 for span in spans),
            }
            if block_rows and abs(block_rows[-1][0]["bbox"][1] - item["bbox"][1]) <= 2:
                block_rows[-1].append(item)
            else:
                block_rows.append([item])

        for same_line in block_rows:
            same_line.sort(key=lambda item: item["bbox"][0])
            pieces: list[str] = []
            previous_x1: float | None = None
            for item in same_line:
                gap = item["bbox"][0] - previous_x1 if previous_x1 is not None else 0
                pieces.append(
                    (" | " if gap > 15 else " ") + item["text"] if pieces else item["text"]
                )
                previous_x1 = item["bbox"][2]
            rows.append(
                {
                    "text": "".join(pieces),
                    "bbox": [
                        min(item["bbox"][0] for item in same_line),
                        min(item["bbox"][1] for item in same_line),
                        max(item["bbox"][2] for item in same_line),
                        max(item["bbox"][3] for item in same_line),
                    ],
                    "font_size": max(item["font_size"] for item in same_line),
                    "bold": any(item["bold"] for item in same_line),
                    "block_index": block_index,
                }
            )

    groups: list[list[dict[str, Any]]] = []
    for row in rows:
        if not groups or _starts_logical_region(row, groups[-1]):
            groups.append([row])
        else:
            groups[-1].append(row)

    regions: list[dict[str, Any]] = []
    for group in groups:
        text = " ".join(row["text"].strip() for row in group).strip()
        bbox = [
            min(row["bbox"][0] for row in group),
            min(row["bbox"][1] for row in group),
            max(row["bbox"][2] for row in group),
            max(row["bbox"][3] for row in group),
        ]
        font_size = max(row["font_size"] for row in group)
        regions.append(
            {
                "id": f"region-{page_index + 1}-{len(regions) + 1}",
                "type": _region_label(
                    text, bbox, page_height, font_size, bold=any(row["bold"] for row in group)
                ),
                "bbox": _box(bbox),
                "text": text,
                "font_size": round(font_size, 2),
                "reading_order": len(regions),
                "_source_order": group[0]["block_index"],
            }
        )
    return regions


def _starts_logical_region(row: dict[str, Any], current: list[dict[str, Any]]) -> bool:
    text = row["text"].strip()
    current_text = " ".join(item["text"] for item in current).strip()
    bullet = bool(LIST_MARKER_RE.match(text))
    current_bullet = bool(LIST_MARKER_RE.match(current_text))
    heading = row["font_size"] >= 11.5 and row["bold"] and len(text) < 100
    current_heading = (
        current[0]["font_size"] >= 11.5 and current[0]["bold"] and len(current_text) < 100
    )
    field_label = bool(re.match(r"^[A-Za-z][A-Za-z &/+.-]{1,35}:\s", text))
    gap = row["bbox"][1] - current[-1]["bbox"][3]

    if heading or current_heading or bullet or field_label:
        return True
    if current_bullet:
        if row["bold"] and row["bbox"][0] <= current[0]["bbox"][0] + 2:
            return True
        return gap > 5 or row["bbox"][0] <= current[0]["bbox"][0] + 2
    if row["bold"] and row["bbox"][0] <= 35 and (DATE_RANGE_RE.search(current_text) or gap > 4):
        return True
    return row["block_index"] != current[-1]["block_index"]


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
                    "method": "pymupdf-vector",
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
            regions = _extract_text_regions(page_dict, page_index, page.rect.height)
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
                            "id": "",
                            "type": "image",
                            "bbox": bbox,
                            "text": "",
                            "font_size": 0,
                            "reading_order": 0,
                            "_source_order": block_index,
                        }
                    )

            regions.sort(key=lambda region: (region.pop("_source_order"), region["bbox"][1]))
            for region_index, region in enumerate(regions, start=1):
                region["id"] = f"region-{page_index + 1}-{region_index}"
                region["reading_order"] = region_index - 1
                total_text += len(region.get("text", ""))

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
            ocr_tables = extract_ocr_tables(
                page_index + 1,
                regions,
                preprocessing,
                start_index=len(tables),
            )
            if ocr_tables:
                tables.extend(ocr_tables)
                total_tables += len(ocr_tables)
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
