from documind.qa import answer_question

DOCUMENT = {
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
    ]
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
