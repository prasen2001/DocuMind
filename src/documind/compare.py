from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .qa import answer_question

WORD_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._%-]+")
COMMON_WORDS = {
    "about",
    "after",
    "also",
    "been",
    "document",
    "from",
    "have",
    "into",
    "more",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "with",
    "were",
}


def _terms(text: str) -> set[str]:
    return {
        word.lower()
        for word in WORD_RE.findall(text)
        if len(word) > 3 and word.lower() not in COMMON_WORDS
    }


def compare_documents(documents: list[dict[str, Any]], question: str) -> dict[str, Any]:
    """Answer the same question independently and align the evidence by document."""
    if len(documents) < 2:
        raise ValueError("Choose at least two documents to compare")
    if len(documents) > 10:
        raise ValueError("At most ten documents can be compared at once")
    question = question.strip()
    if not question:
        raise ValueError("A comparison question is required")

    results: list[dict[str, Any]] = []
    grounded_term_sets: list[set[str]] = []
    for document in documents:
        answer = answer_question(document, question, limit=2)
        results.append(
            {
                "document_id": document["id"],
                "filename": document["filename"],
                **answer,
            }
        )
        if answer["grounded"]:
            grounded_term_sets.append(_terms(answer["answer"]))

    term_frequency = Counter(term for terms in grounded_term_sets for term in terms)
    common_terms = sorted(
        term for term, count in term_frequency.items() if count == len(grounded_term_sets)
    )
    for result in results:
        own_terms = _terms(result["answer"]) if result["grounded"] else set()
        result["distinct_terms"] = sorted(own_terms - set(common_terms))[:12]

    grounded_count = sum(result["grounded"] for result in results)
    return {
        "question": question,
        "method": "parallel-evidence-retrieval",
        "document_count": len(documents),
        "grounded_document_count": grounded_count,
        "common_terms": common_terms[:12],
        "results": results,
        "notice": "Each result is retrieved independently; absence of evidence is shown explicitly.",
    }
