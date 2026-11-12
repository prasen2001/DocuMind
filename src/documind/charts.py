from __future__ import annotations

import re
from typing import Any

import pymupdf

NUMBER_RE = re.compile(r"(?<!\w)(?:[$€£])?-?\d[\d,.]*(?:%|[KMB])?(?!\w)", re.IGNORECASE)
CHART_TITLE_RE = re.compile(
    r"\b(chart|figure|trend|growth|revenue|margin|distribution)\b", re.IGNORECASE
)


def _box(rect: pymupdf.Rect) -> list[float]:
    return [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)]


def _expanded(rect: pymupdf.Rect, amount: float) -> pymupdf.Rect:
    return pymupdf.Rect(rect.x0 - amount, rect.y0 - amount, rect.x1 + amount, rect.y1 + amount)


def _drawing_rect(drawing: dict[str, Any]) -> pymupdf.Rect:
    rect = pymupdf.Rect(drawing["rect"])
    if rect.width < 1:
        rect.x0 -= 0.5
        rect.x1 += 0.5
    if rect.height < 1:
        rect.y0 -= 0.5
        rect.y1 += 0.5
    return rect


def _cluster_drawings(drawings: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    clusters: list[list[dict[str, Any]]] = []
    for drawing in drawings:
        rect = _drawing_rect(drawing)
        matching: list[int] = []
        for index, cluster in enumerate(clusters):
            union = _drawing_rect(cluster[0])
            for item in cluster[1:]:
                union |= _drawing_rect(item)
            if _expanded(union, 28).intersects(rect):
                matching.append(index)
        if not matching:
            clusters.append([drawing])
            continue
        primary = matching[0]
        clusters[primary].append(drawing)
        for index in reversed(matching[1:]):
            clusters[primary].extend(clusters.pop(index))
    return clusters


def extract_charts(page: pymupdf.Page, regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect likely vector charts and retain values with their source regions."""
    try:
        drawings = page.get_drawings()
    except (RuntimeError, ValueError):
        return []

    page_area = max(1.0, page.rect.width * page.rect.height)
    charts: list[dict[str, Any]] = []
    for cluster in _cluster_drawings(drawings):
        if len(cluster) < 4:
            continue
        rect = _drawing_rect(cluster[0])
        for drawing in cluster[1:]:
            rect |= _drawing_rect(drawing)
        if rect.width < 100 or rect.height < 60 or rect.get_area() > page_area * 0.85:
            continue

        rectangle_count = 0
        line_count = 0
        for drawing in cluster:
            for item in drawing.get("items", []):
                if item[0] == "re":
                    rectangle_count += 1
                elif item[0] in {"l", "c"}:
                    line_count += 1
        chart_type = "bar" if rectangle_count >= 3 else "line" if line_count >= 3 else "unknown"

        context = _expanded(rect, 45)
        related_regions = [
            region
            for region in regions
            if region.get("text") and context.intersects(pymupdf.Rect(region["bbox"]))
        ]
        title_candidates = [
            region
            for region in related_regions
            if region["bbox"][3] <= rect.y0 + 12
            and (
                region.get("type") in {"title", "heading", "caption"}
                or CHART_TITLE_RE.search(region["text"])
            )
        ]
        title = (
            min(title_candidates, key=lambda region: abs(rect.y0 - region["bbox"][3]))["text"]
            if title_candidates
            else ""
        )
        values: list[dict[str, Any]] = []
        for region in related_regions:
            for match in NUMBER_RE.finditer(region["text"]):
                values.append(
                    {
                        "raw": match.group(0),
                        "region_id": region["id"],
                        "bbox": region["bbox"],
                    }
                )
        label_text = [region["text"] for region in related_regions if region["text"] != title]
        charts.append(
            {
                "id": f"chart-{page.number + 1}-{len(charts) + 1}",
                "bbox": _box(rect),
                "type": chart_type,
                "title": title,
                "labels": label_text,
                "values": values,
                "drawing_count": len(cluster),
                "confidence": round(min(0.95, 0.5 + len(cluster) * 0.04), 2),
                "method": "vector-geometry",
            }
        )
    return charts
