import pytest

from documind.compare import compare_documents


def document(document_id: str, filename: str, text: str) -> dict:
    return {
        "id": document_id,
        "filename": filename,
        "pages": [
            {
                "number": 1,
                "regions": [
                    {
                        "id": f"region-{document_id}",
                        "type": "paragraph",
                        "bbox": [10, 20, 300, 50],
                        "text": text,
                    }
                ],
            }
        ],
    }


def test_compares_documents_without_mixing_evidence() -> None:
    result = compare_documents(
        [
            document("a", "first.pdf", "Revenue increased to 4.2 million dollars."),
            document("b", "second.pdf", "Revenue increased to 5.1 million dollars."),
        ],
        "What revenue was reported?",
    )

    assert result["grounded_document_count"] == 2
    assert result["results"][0]["citations"][0]["region_id"] == "region-a"
    assert result["results"][1]["citations"][0]["region_id"] == "region-b"
    assert "4.2" in result["results"][0]["answer"]
    assert "5.1" in result["results"][1]["answer"]


def test_requires_two_documents() -> None:
    with pytest.raises(ValueError, match="at least two"):
        compare_documents([document("a", "only.pdf", "Revenue was 1 million.")], "Revenue?")
