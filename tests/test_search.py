from documind.search import search_documents


def test_searches_regions_across_documents_with_source_coordinates() -> None:
    documents = [
        {
            "id": "a",
            "filename": "alpha.pdf",
            "pages": [
                {
                    "number": 2,
                    "regions": [
                        {
                            "id": "a-r1",
                            "type": "paragraph",
                            "bbox": [10, 20, 300, 40],
                            "text": "Operating revenue increased substantially.",
                        }
                    ],
                }
            ],
        },
        {
            "id": "b",
            "filename": "beta.pdf",
            "pages": [
                {
                    "number": 1,
                    "regions": [
                        {
                            "id": "b-r1",
                            "type": "paragraph",
                            "bbox": [15, 25, 320, 55],
                            "text": "Headcount remained stable.",
                        }
                    ],
                }
            ],
        },
    ]

    result = search_documents(documents, "revenue increase")

    assert result["total"] == 1
    assert result["matches"][0]["document_id"] == "a"
    assert result["matches"][0]["page"] == 2
    assert result["matches"][0]["bbox"] == [10, 20, 300, 40]


def test_empty_search_abstains() -> None:
    result = search_documents([], "")
    assert result["matches"] == []
    assert result["total"] == 0
