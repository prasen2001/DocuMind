from __future__ import annotations

import importlib.util
from typing import Any

import pymupdf


def vision_available() -> bool:
    return (
        importlib.util.find_spec("cv2") is not None
        and importlib.util.find_spec("numpy") is not None
    )


def preprocess_page(page: pymupdf.Page, *, scale: float = 2.0) -> dict[str, Any] | None:
    """Deskew, threshold, and detect structural line boxes on a rendered page."""
    if not vision_available():
        return None
    import cv2  # type: ignore[import-not-found]
    import numpy as np

    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale), alpha=False, colorspace=pymupdf.csGRAY
    )
    gray = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        15,
    )
    ink = 255 - binary
    coordinates = np.column_stack(np.where(ink > 0))
    skew = 0.0
    if len(coordinates) >= 20:
        raw_angle = cv2.minAreaRect(coordinates[:, ::-1].astype(np.float32))[-1]
        skew = float(-(90 + raw_angle) if raw_angle > 45 else -raw_angle)
        if abs(skew) > 15:
            skew = 0.0
    if abs(skew) >= 0.1:
        center = (gray.shape[1] / 2, gray.shape[0] / 2)
        matrix = cv2.getRotationMatrix2D(center, skew, 1.0)
        gray = cv2.warpAffine(
            gray,
            matrix,
            (gray.shape[1], gray.shape[0]),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            15,
        )
        ink = 255 - binary

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, gray.shape[1] // 30), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, gray.shape[0] // 30)))
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, vertical_kernel)
    structure = cv2.bitwise_or(horizontal, vertical)
    contours, _ = cv2.findContours(structure, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    structure_boxes: list[list[float]] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width * height < 80 or max(width, height) < 20:
            continue
        structure_boxes.append(
            [
                round(x / scale, 2),
                round(y / scale, 2),
                round((x + width) / scale, 2),
                round((y + height) / scale, 2),
            ]
        )

    success, encoded = cv2.imencode(".png", binary)
    if not success:
        raise RuntimeError("OpenCV could not encode the preprocessed page")
    return {
        "image": encoded.tobytes(),
        "scale": scale,
        "skew_degrees": round(skew, 3),
        "structure_boxes": structure_boxes,
        "render_width": int(gray.shape[1]),
        "render_height": int(gray.shape[0]),
        "steps": ["grayscale", "adaptive-threshold", "deskew", "line-morphology"],
    }
