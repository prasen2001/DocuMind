from collections.abc import Sequence

from documind.qa import answer_question, answer_question_semantic

DOCUMENT = {
    "id": "document-1",
    "filename": "financial-results.pdf",
    "pages": [
        {
            "number": 1,
            "regions": [
                {
                    "id": "region-1-1",
                    "type": "heading",
                    "bbox": [10, 10, 200, 30],
                    "text": "Financial results",
                },
                {
                    "id": "region-1-2",
                    "type": "paragraph",
                    "bbox": [10, 40, 400, 80],
                    "text": "Revenue reached $4.2 million in October. The margin was 18 percent.",
                },
            ],
        }
    ],
}


def test_answer_is_grounded_in_matching_region() -> None:
    result = answer_question(DOCUMENT, "What revenue was reported?")

    assert result["grounded"] is True
    assert "$4.2 million" in result["answer"]
    assert result["citations"][0]["page"] == 1
    assert result["citations"][0]["bbox"] == [10, 40, 400, 80]


def test_answer_abstains_without_evidence() -> None:
    result = answer_question(DOCUMENT, "Who is the chief executive?")

    assert result["grounded"] is False
    assert result["citations"] == []


class SemanticTestEncoder:
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if "turnover" in text.lower() or "revenue" in text.lower() else [0.0, 1.0]
            for text in texts
        ]


def test_semantic_rag_returns_only_cited_source_text() -> None:
    result = answer_question_semantic(
        DOCUMENT, "What turnover was reported?", encoder=SemanticTestEncoder()
    )

    assert result["grounded"] is True
    assert result["method"] == "semantic-extractive-rag"
    assert "$4.2 million" in result["answer"]
    assert result["citations"][0]["bbox"] == [10, 40, 400, 80]
    assert "unsupported text" in result["notice"]
