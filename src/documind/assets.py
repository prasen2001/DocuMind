from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf

MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "jpx": "image/jp2",
    "jp2": "image/jp2",
    "webp": "image/webp",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}


def extract_image_asset(
    source: Path, *, page_number: int, image: dict[str, Any]
) -> tuple[bytes, str]:
    """Return an embedded image, falling back to rendering its page region."""
    with pymupdf.open(source) as document:
        if page_number < 1 or page_number > document.page_count:
            raise FileNotFoundError(page_number)
        xref = int(image.get("xref", 0))
        if xref > 0:
            extracted = document.extract_image(xref)
            payload = extracted.get("image")
            extension = str(extracted.get("ext", image.get("extension", "png"))).lower()
            if payload:
                return payload, MIME_TYPES.get(extension, "application/octet-stream")

        page = document[page_number - 1]
        clip = pymupdf.Rect(image["bbox"]) & page.rect
        if clip.is_empty:
            raise FileNotFoundError(image.get("id", "image"))
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip, alpha=False)
        return pixmap.tobytes("png"), "image/png"
