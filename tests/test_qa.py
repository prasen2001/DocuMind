from collections.abc import Sequence
from datetime import date

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

RESUME = {
    "id": "resume-1",
    "filename": "resume.pdf",
    "pages": [
        {
            "number": 1,
            "regions": [
                {
                    "id": "education-heading",
                    "type": "heading",
                    "bbox": [10, 10, 200, 30],
                    "text": "Education",
                },
                {
                    "id": "degree",
                    "type": "paragraph",
                    "bbox": [10, 35, 400, 55],
                    "text": "University Aug 2019 – Jun 2023",
                },
                {
                    "id": "experience-heading",
                    "type": "heading",
                    "bbox": [10, 60, 200, 80],
                    "text": "Experience",
                },
                {
                    "id": "role-one",
                    "type": "paragraph",
                    "bbox": [10, 85, 400, 115],
                    "text": "Senior Software Engineer Sep 2025 – Aug 2026",
                },
                {
                    "id": "role-two",
                    "type": "paragraph",
                    "bbox": [10, 120, 400, 150],
                    "text": "Software Engineer Jul 2023 – Jun 2025",
                },
                {
                    "id": "projects-heading",
                    "type": "heading",
                    "bbox": [10, 155, 200, 175],
                    "text": "Projects",
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


def test_answer_calculates_resume_experience_from_dated_roles() -> None:
    result = answer_question(RESUME, "How many years of experience is present?")

    assert result["grounded"] is True
    assert result["method"] == "resume-experience-date-analysis"
    assert "3 years" in result["answer"]
    assert len(result["citations"]) == 2
    assert {citation["region_id"] for citation in result["citations"]} == {
        "role-one",
        "role-two",
    }


def test_resume_experience_handles_present_and_overlapping_roles() -> None:
    resume = {
        **RESUME,
        "pages": [
            {
                **RESUME["pages"][0],
                "regions": [
                    *RESUME["pages"][0]["regions"][:3],
                    {
                        "id": "current-role",
                        "type": "paragraph",
                        "bbox": [10, 85, 400, 115],
                        "text": "Engineer Jan 2024 - Present",
                    },
                    {
                        "id": "overlap-role",
                        "type": "paragraph",
                        "bbox": [10, 120, 400, 150],
                        "text": "Consultant Jan 2025 to Dec 2025",
                    },
                    RESUME["pages"][0]["regions"][-1],
                ],
            }
        ],
    }

    result = answer_question(
        resume,
        "What is the total professional experience?",
        reference_date=date(2026, 11, 12),
    )

    assert "2 years and 11 months" in result["answer"]
    assert "counted only once" in result["answer"]


def test_ai_experience_diversifies_evidence_across_roles() -> None:
    resume = {
        **RESUME,
        "pages": [
            {
                **RESUME["pages"][0],
                "regions": [
                    *RESUME["pages"][0]["regions"][:4],
                    {
                        "id": "insaito-ai",
                        "type": "paragraph",
                        "bbox": [10, 116, 400, 135],
                        "text": "Built an AI agent platform with multi-agent orchestration and RAG.",
                    },
                    RESUME["pages"][0]["regions"][4],
                    {
                        "id": "fold-ai",
                        "type": "paragraph",
                        "bbox": [10, 151, 400, 170],
                        "text": "Delivered an LLM-powered EHR synopsis using LangChain.",
                    },
                    RESUME["pages"][0]["regions"][-1],
                ],
            }
        ],
    }

    result = answer_question(resume, "Does the candidate have AI experience?")

    assert result["grounded"] is True
    assert result["method"] == "resume-ai-experience-analysis"
    assert "2 dated roles" in result["answer"]
    assert {citation["region_id"] for citation in result["citations"]} == {
        "insaito-ai",
        "fold-ai",
    }


def test_semantic_ai_question_uses_role_diverse_analysis() -> None:
    resume = {
        **RESUME,
        "pages": [
            {
                **RESUME["pages"][0],
                "regions": [
                    *RESUME["pages"][0]["regions"][:-1],
                    {
                        "id": "fold-ai",
                        "type": "paragraph",
                        "bbox": [10, 151, 400, 170],
                        "text": "Delivered an LLM-powered clinical application.",
                    },
                    RESUME["pages"][0]["regions"][-1],
                ],
            }
        ],
    }

    result = answer_question_semantic(
        resume, "Does this person have an LLM background?", encoder=SemanticTestEncoder()
    )

    assert result["method"] == "resume-ai-experience-analysis"
    assert result["citations"][0]["region_id"] == "fold-ai"


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
