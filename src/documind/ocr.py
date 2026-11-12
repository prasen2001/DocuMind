from __future__ import annotations

import csv
import io
import shutil
import subprocess
from collections import defaultdict
from typing import Any

import pymupdf


def tesseract_path() -> str | None:
    """Return the installed Tesseract executable, if available."""
    return shutil.which("tesseract")


def ocr_available() -> bool:
    return tesseract_path() is not None


def extract_ocr_regions(
    page: pymupdf.Page, *, scale: float = 2.0, image_bytes: bytes | None = None
) -> list[dict[str, Any]]:
    """Recognize a page and map Tesseract TSV coordinates back into PDF points."""
    executable = tesseract_path()
    if executable is None:
        return []

    if image_bytes is None:
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), alpha=False, colorspace=pymupdf.csRGB
        )
        image_bytes = pixmap.tobytes("png")
    try:
        completed = subprocess.run(
            [executable, "stdin", "stdout", "-l", "eng", "--psm", "3", "tsv"],
            input=image_bytes,
            capture_output=True,
            check=False,
            timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Tesseract OCR timed out") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "Tesseract OCR failed")

    rows = csv.DictReader(
        io.StringIO(completed.stdout.decode("utf-8", errors="replace")), delimiter="\t"
    )
    lines: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        text = (row.get("text") or "").strip()
        try:
            confidence = float(row.get("conf", "-1"))
        except ValueError:
            confidence = -1
        if not text or confidence < 0:
            continue
        key = tuple(
            row.get(field, "0") for field in ("page_num", "block_num", "par_num", "line_num")
        )
        lines[key].append(
            {
                "text": text,
                "confidence": confidence,
                "left": int(row.get("left", "0")),
                "top": int(row.get("top", "0")),
                "width": int(row.get("width", "0")),
                "height": int(row.get("height", "0")),
            }
        )

    regions: list[dict[str, Any]] = []
    for words in lines.values():
        left = min(word["left"] for word in words)
        top = min(word["top"] for word in words)
        right = max(word["left"] + word["width"] for word in words)
        bottom = max(word["top"] + word["height"] for word in words)
        regions.append(
            {
                "type": "ocr_text",
                "bbox": [
                    round(left / scale, 2),
                    round(top / scale, 2),
                    round(right / scale, 2),
                    round(bottom / scale, 2),
                ],
                "text": " ".join(word["text"] for word in words),
                "font_size": 0,
                "confidence": round(sum(word["confidence"] for word in words) / len(words), 2),
                "source": "tesseract",
                "words": [
                    {
                        "text": word["text"],
                        "confidence": round(word["confidence"], 2),
                        "bbox": [
                            round(word["left"] / scale, 2),
                            round(word["top"] / scale, 2),
                            round((word["left"] + word["width"]) / scale, 2),
                            round((word["top"] + word["height"]) / scale, 2),
                        ],
                    }
                    for word in words
                ],
            }
        )
    return sorted(regions, key=lambda region: (region["bbox"][1], region["bbox"][0]))
