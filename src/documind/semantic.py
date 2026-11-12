from __future__ import annotations

import importlib.util
import math
import os
import threading
from collections.abc import Sequence
from typing import Any, Protocol

DEFAULT_MODEL = "microsoft/MiniLM-L12-H384-uncased"


class SemanticUnavailable(RuntimeError):
    pass


class Encoder(Protocol):
    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


def semantic_available() -> bool:
    return (
        os.environ.get("DOCUMIND_ENABLE_SEMANTIC", "0") == "1"
        and importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("transformers") is not None
    )


class MiniLMEncoder:
    """Lazy Microsoft MiniLM mean-pooling encoder."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        if not semantic_available():
            raise SemanticUnavailable(
                "Semantic search requires the semantic extra and DOCUMIND_ENABLE_SEMANTIC=1"
            )
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        torch = self.torch
        encoded = self.tokenizer(
            list(texts), padding=True, truncation=True, max_length=256, return_tensors="pt"
        )
        with torch.no_grad():
            output = self.model(**encoded).last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).expand(output.size()).float()
        pooled = (output * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return pooled.cpu().tolist()


_encoder: MiniLMEncoder | None = None
_encoder_lock = threading.Lock()


def default_encoder() -> MiniLMEncoder:
    global _encoder
    with _encoder_lock:
        if _encoder is None:
            _encoder = MiniLMEncoder(os.environ.get("DOCUMIND_SEMANTIC_MODEL", DEFAULT_MODEL))
        return _encoder


def _cosine(first: Sequence[float], second: Sequence[float]) -> float:
    numerator = sum(left * right for left, right in zip(first, second, strict=True))
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    return numerator / (first_norm * second_norm) if first_norm and second_norm else 0.0


def semantic_search_documents(
    documents: list[dict[str, Any]],
    query: str,
    *,
    limit: int = 20,
    encoder: Encoder | None = None,
) -> dict[str, Any]:
    query = query.strip()
    if not query:
        return {"query": query, "matches": [], "total": 0, "method": "minilm-vector-search"}
    corpus: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for document in documents:
        for page in document.get("pages", []):
            for region in page.get("regions", []):
                if region.get("text", "").strip():
                    corpus.append((document, page, region))
    if not corpus:
        return {"query": query, "matches": [], "total": 0, "method": "minilm-vector-search"}

    selected_encoder = encoder or default_encoder()
    vectors = selected_encoder.encode([query, *(region["text"] for _, _, region in corpus)])
    if len(vectors) != len(corpus) + 1:
        raise ValueError("Semantic encoder returned an unexpected vector count")
    query_vector = vectors[0]
    matches: list[dict[str, Any]] = []
    for (document, page, region), vector in zip(corpus, vectors[1:], strict=True):
        score = _cosine(query_vector, vector)
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
        "method": "minilm-vector-search",
        "model": os.environ.get("DOCUMIND_SEMANTIC_MODEL", DEFAULT_MODEL),
    }
