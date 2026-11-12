from __future__ import annotations

from itertools import pairwise
from typing import Any


def _boundaries(lines: list[list[float]], *, vertical: bool) -> list[float]:
    values = [((line[0] + line[2]) / 2 if vertical else (line[1] + line[3]) / 2) for line in lines]
    merged: list[float] = []
    for value in sorted(values):
        if not merged or abs(value - merged[-1]) > 3:
            merged.append(value)
        else:
            merged[-1] = (merged[-1] + value) / 2
    return merged


def extract_ocr_tables(
    page_number: int,
    regions: list[dict[str, Any]],
    preprocessing: dict[str, Any] | None,
    *,
    start_index: int = 0,
) -> list[dict[str, Any]]:
    """Reconstruct grid cells from CV line boundaries and OCR word centers."""
    if not preprocessing:
        return []
    horizontal = preprocessing.get("horizontal_lines", [])
    vertical = preprocessing.get("vertical_lines", [])
    x_boundaries = _boundaries(vertical, vertical=True)
    y_boundaries = _boundaries(horizontal, vertical=False)
    if len(x_boundaries) < 2 or len(y_boundaries) < 2:
        return []

    words = [word for region in regions for word in region.get("words", [])]
    if not words:
        return []
    rows: list[list[str]] = []
    for top, bottom in pairwise(y_boundaries):
        row: list[str] = []
        for left, right in pairwise(x_boundaries):
            cell_words = []
            for word in words:
                x0, y0, x1, y1 = word["bbox"]
                center_x, center_y = (x0 + x1) / 2, (y0 + y1) / 2
                if left <= center_x <= right and top <= center_y <= bottom:
                    cell_words.append(word)
            cell_words.sort(key=lambda word: (word["bbox"][1], word["bbox"][0]))
            row.append(" ".join(word["text"] for word in cell_words))
        rows.append(row)
    if not any(cell for row in rows for cell in row):
        return []
    return [
        {
            "id": f"table-{page_number}-{start_index + 1}",
            "bbox": [
                round(x_boundaries[0], 2),
                round(y_boundaries[0], 2),
                round(x_boundaries[-1], 2),
                round(y_boundaries[-1], 2),
            ],
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(rows[0]) if rows else 0,
            "method": "opencv-grid-tesseract",
        }
    ]
