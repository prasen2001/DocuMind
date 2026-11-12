from __future__ import annotations

import re
from itertools import pairwise
from typing import Any

CAPTION_RE = re.compile(r"^(figure|fig\.?|table|chart|exhibit)\s*[\dA-Z.-]*[:.]?\s", re.IGNORECASE)


def _vertical_distance(first: list[float], second: list[float]) -> float:
    if first[3] < second[1]:
        return second[1] - first[3]
    if second[3] < first[1]:
        return first[1] - second[3]
    return 0.0


def infer_relationships(
    page_number: int,
    regions: list[dict[str, Any]],
    images: list[dict[str, Any]],
    tables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create deterministic reading-order and caption relationships."""
    relationships: list[dict[str, Any]] = []
    text_regions = [region for region in regions if region.get("text")]
    for previous, current in pairwise(text_regions):
        relationships.append(
            {
                "type": "precedes",
                "source_id": previous["id"],
                "target_id": current["id"],
                "confidence": 1.0,
                "method": "reading-order",
            }
        )

    visual_targets = [
        *(dict(item, target_type="image") for item in images),
        *(dict(item, target_type="table") for item in tables),
    ]
    for region in text_regions:
        if not CAPTION_RE.match(region["text"].strip()) or not visual_targets:
            continue
        target = min(
            visual_targets, key=lambda item: _vertical_distance(region["bbox"], item["bbox"])
        )
        distance = _vertical_distance(region["bbox"], target["bbox"])
        page_height_hint = max(region["bbox"][3], target["bbox"][3], 1)
        if distance > page_height_hint * 0.2:
            continue
        relationships.append(
            {
                "type": "caption_of",
                "source_id": region["id"],
                "target_id": target["id"],
                "target_type": target["target_type"],
                "page": page_number,
                "confidence": round(max(0.5, 1 - distance / page_height_hint), 3),
                "method": "caption-proximity",
            }
        )
        region["type"] = "caption"
    return relationships
