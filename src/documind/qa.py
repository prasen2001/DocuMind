from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .semantic import Encoder, semantic_search_documents

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in STOP_WORDS]


def answer_question(document: dict[str, Any], question: str, *, limit: int = 3) -> dict[str, Any]:
    """Retrieve answer-sized passages while preserving their exact source regions."""
    query_tokens = _tokens(question)
    if not query_tokens:
        return _abstention(question, "Please ask a more specific question.")

    candidates: list[dict[str, Any]] = []
    region_token_sets: list[set[str]] = []
    regions: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for page in document.get("pages", []):
        for region in page.get("regions", []):
            if not region.get("text"):
                continue
            regions.append((page, region))
            region_token_sets.append(set(_tokens(region["text"])))

    document_frequency = Counter(token for tokens in region_token_sets for token in tokens)
    corpus_size = max(1, len(regions))
    for (page, region), token_set in zip(regions, region_token_sets, strict=True):
        overlap = set(query_tokens) & token_set
        if not overlap:
            continue
        idf_score = sum(
            math.log((corpus_size + 1) / (document_frequency[t] + 1)) + 1 for t in overlap
        )
        coverage = len(overlap) / len(set(query_tokens))
        heading_bonus = 0.25 if region.get("type") in {"title", "heading"} else 0
        score = idf_score * (0.5 + coverage) + heading_bonus
        candidates.append({"score": score, "page": page, "region": region})

    if not candidates:
        return _abstention(question, "I could not find relevant evidence in this document.")

    candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
    selected = candidates[:limit]
    citations: list[dict[str, Any]] = []
    answer_parts: list[str] = []
    for rank, candidate in enumerate(selected, start=1):
        page = candidate["page"]
        region = candidate["region"]
        sentences = [part.strip() for part in SENTENCE_RE.split(region["text"]) if part.strip()]
        sentence = max(
            sentences or [region["text"]],
            key=lambda value: len(set(_tokens(value)) & set(query_tokens)),
        )
        if sentence not in answer_parts:
            answer_parts.append(sentence)
        citations.append(
            {
                "id": f"citation-{rank}",
                "page": page["number"],
                "bbox": region["bbox"],
                "region_id": region["id"],
                "quote": sentence[:500],
                "score": round(candidate["score"], 3),
            }
        )

    return {
        "question": question,
        "answer": " ".join(answer_parts),
        "grounded": True,
        "method": "lexical-evidence-retrieval",
        "citations": citations,
        "notice": "This answer is extracted from matching source passages; it is not model-generated.",
    }


def answer_question_semantic(
    document: dict[str, Any],
    question: str,
    *,
    limit: int = 3,
    encoder: Encoder | None = None,
) -> dict[str, Any]:
    """Retrieve semantically similar evidence and return only extractive source text."""
    result = semantic_search_documents([document], question, limit=limit, encoder=encoder)
    matches = [match for match in result["matches"] if match["score"] > 0]
    if not matches:
        return _abstention(
            question, "I could not find relevant semantic evidence in this document."
        )
    citations = [
        {
            "id": f"citation-{index}",
            "page": match["page"],
            "bbox": match["bbox"],
            "region_id": match["region_id"],
            "quote": match["quote"],
            "score": match["score"],
        }
        for index, match in enumerate(matches, start=1)
    ]
    return {
        "question": question,
        "answer": " ".join(match["quote"] for match in matches),
        "grounded": True,
        "method": "semantic-extractive-rag",
        "model": result.get("model"),
        "citations": citations,
        "notice": "This answer contains only retrieved source text; no unsupported text was generated.",
    }


def _abstention(question: str, message: str) -> dict[str, Any]:
    return {
        "question": question,
        "answer": message,
        "grounded": False,
        "method": "lexical-evidence-retrieval",
        "citations": [],
        "notice": "No answer was produced without supporting document evidence.",
    }
