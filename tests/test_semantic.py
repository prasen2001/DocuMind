from collections.abc import Sequence
from typing import ClassVar

from documind.semantic import semantic_search_documents


class MeaningEncoder:
    vectors: ClassVar[dict[str, list[float]]] = {
        "turnover": [1.0, 0.0],
        "Revenue reached four million dollars.": [0.95, 0.05],
        "Employee headcount stayed stable.": [0.0, 1.0],
    }

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.vectors[text] for text in texts]


def test_semantic_search_matches_meaning_without_token_overlap() -> None:
    document = {
        "id": "doc",
        "filename": "report.pdf",
        "pages": [
            {
                "number": 1,
                "regions": [
                    {
                        "id": "revenue",
                        "type": "paragraph",
                        "bbox": [10, 10, 300, 30],
                        "text": "Revenue reached four million dollars.",
                    },
                    {
                        "id": "people",
                        "type": "paragraph",
                        "bbox": [10, 40, 300, 60],
                        "text": "Employee headcount stayed stable.",
                    },
                ],
            }
        ],
    }

    result = semantic_search_documents([document], "turnover", encoder=MeaningEncoder())

    assert result["matches"][0]["region_id"] == "revenue"
    assert result["matches"][0]["score"] > 0.9
    assert result["matches"][0]["bbox"] == [10, 10, 300, 30]
