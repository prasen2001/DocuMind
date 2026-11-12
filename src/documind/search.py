from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._%-]+")


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def search_documents(
    documents: list[dict[str, Any]], query: str, *, limit: int = 20
) -> dict[str, Any]:
    """Search evidence regions across documents using a compact BM25-style score."""
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return {"query": query, "matches": [], "total": 0, "method": "lexical-region-search"}

    corpus: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]] = []
    for document in documents:
        for page in document.get("pages", []):
            for region in page.get("regions", []):
                tokens = _tokens(region.get("text", ""))
                if tokens:
                    corpus.append((document, page, region, tokens))

    document_frequency = Counter(token for *_, tokens in corpus for token in set(tokens))
    average_length = sum(len(item[3]) for item in corpus) / max(1, len(corpus))
    matches: list[dict[str, Any]] = []
    for document, page, region, tokens in corpus:
        frequencies = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            if not frequencies[token]:
                continue
            inverse_frequency = math.log(
                1
                + (len(corpus) - document_frequency[token] + 0.5)
                / (document_frequency[token] + 0.5)
            )
            saturation = (
                frequencies[token]
                * 2.2
                / (frequencies[token] + 1.2 * (0.25 + 0.75 * len(tokens) / max(1, average_length)))
            )
            score += inverse_frequency * saturation
        if score <= 0:
            continue
        matches.append(
            {
                "document_id": document["id"],
                "filename": document["filename"],
                "page": page["number"],
                "region_id": region["id"],
                "region_type": region["type"],
                "bbox": region["bbox"],
                "quote": region["text"][:700],
                "score": round(score, 4),
            }
        )
    matches.sort(key=lambda match: match["score"], reverse=True)
    return {
        "query": query,
        "matches": matches[: max(1, min(limit, 100))],
        "total": len(matches),
        "method": "bm25-region-search",
    }
