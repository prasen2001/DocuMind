from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date
from typing import Any

from .semantic import Encoder, semantic_search_documents

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
MONTHS = {
    name.lower(): number
    for number, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for name in names
}
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_RANGE_RE = re.compile(
    rf"\b(?P<start_month>{MONTH_PATTERN})\.?\s+(?P<start_year>\d{{4}})\s*"
    rf"(?:[-–—]|\bto\b)\s*"
    rf"(?:(?P<end_month>{MONTH_PATTERN})\.?\s+(?P<end_year>\d{{4}})|(?P<present>present|current|now))\b",
    re.IGNORECASE,
)
EXPERIENCE_QUESTION_RE = re.compile(
    r"\bexperience\b.*(?:\byears?\b|\bmonths?\b|\bhow long\b|\btotal\b)"
    r"|(?:\byears?\b|\bmonths?\b|\bhow long\b|\btotal\b).*\bexperience\b",
    re.IGNORECASE,
)
AI_EXPERIENCE_QUESTION_RE = re.compile(
    r"(?:\bai\b|artificial intelligence|\bllms?\b|machine learning).{0,80}"
    r"(?:\bexperience\b|\bbackground\b|\bworked\b|\bwork\b|\bknows?\b|\bknowledge\b|"
    r"\bfamiliar(?:ity)?\b|\bskills?\b|\bexpertise\b)"
    r"|(?:\bexperience\b|\bbackground\b|\bworked\b|\bwork\b|\bknows?\b|\bknowledge\b|"
    r"\bfamiliar(?:ity)?\b|\bskills?\b|\bexpertise\b).{0,80}"
    r"(?:\bai\b|artificial intelligence|\bllms?\b|machine learning)",
    re.IGNORECASE,
)
AI_SCORE_QUESTION_RE = re.compile(
    r"\b(?:score|rate|rating|rank|evaluate|assessment)\b.*"
    r"(?:\bai\b|artificial intelligence|machine learning|\bllm\b).{0,80}\brole\b"
    r"|\b(?:ai|artificial intelligence|machine learning|llm)\b.{0,80}\brole\b.*"
    r"\b(?:score|rate|rating|rank|evaluate|assessment)\b",
    re.IGNORECASE,
)
PROJECT_QUESTION_RE = re.compile(
    r"\bprojects?\b.*(?:\bcompleted\b|\bbuilt\b|\bcreated\b|\bdeveloped\b|\bworked\b|\bcandidate\b)"
    r"|(?:\bcompleted\b|\bbuilt\b|\bcreated\b|\bdeveloped\b|\bworked\b|\bcandidate\b).*\bprojects?\b",
    re.IGNORECASE,
)
ACHIEVEMENT_QUESTION_RE = re.compile(
    r"(?:\bhighlight\b|\bshow\b|\blist\b|\bwhat\b|\bwhich\b).{0,60}"
    r"\b(?:achievements?|awards?|certifications?|honors?)\b"
    r"|\b(?:achievements?|awards?|certifications?|honors?)\b.{0,60}"
    r"(?:\bhighlight\b|\bshow\b|\blist\b|\bcandidate\b|\bresume\b)",
    re.IGNORECASE,
)
RESUME_LIST_MARKER_RE = re.compile(r"^(?:[•●▪◦*–—-]|\d+[.)])\s+")
AI_EVIDENCE_RE = re.compile(
    r"\b(?:ai|artificial intelligence|llms?|large language models?|multi-agent|agentic|rag|"
    r"retrieval-augmented generation|langchain|machine learning|ml inference|model inference|"
    r"document intelligence|vlms?|vision-language models?)\b",
    re.IGNORECASE,
)
AI_CAPABILITIES = (
    (re.compile(r"\b(?:multi-agent|agentic|ai agent)\b", re.IGNORECASE), "AI agents"),
    (
        re.compile(r"\b(?:rag|retrieval-augmented generation)\b", re.IGNORECASE),
        "retrieval-augmented generation",
    ),
    (
        re.compile(
            r"\b(?:document intelligence|ocr|vlms?|vision-language models?)\b", re.IGNORECASE
        ),
        "document AI",
    ),
    (
        re.compile(
            r"\b(?:llms?|large language models?|langchain|model inference)\b", re.IGNORECASE
        ),
        "LLM applications",
    ),
    (re.compile(r"\bmachine learning\b", re.IGNORECASE), "machine learning"),
)
EXPERIENCE_HEADINGS = {"experience", "work experience", "professional experience", "employment"}
PROJECT_HEADINGS = {"projects", "project experience", "personal projects", "selected projects"}
ACHIEVEMENT_HEADINGS = {
    "achievements",
    "achievements & certifications",
    "awards",
    "certifications",
    "honors",
    "honors & awards",
}
SECTION_HEADINGS = {
    "education",
    "projects",
    "project experience",
    "technical skills",
    "skills",
    "achievements",
    "achievements & certifications",
    "certifications",
    "publications",
    "awards",
    "honors",
    "honors & awards",
    "personal projects",
    "selected projects",
}
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


def answer_question(
    document: dict[str, Any],
    question: str,
    *,
    limit: int = 3,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Retrieve answer-sized passages while preserving their exact source regions."""
    analytical_answer = (
        _answer_ai_role_score(document, question)
        or _answer_ai_experience(document, question)
        or _answer_experience_duration(document, question, reference_date)
        or _answer_resume_projects(document, question)
        or _answer_resume_achievements(document, question)
    )
    if analytical_answer:
        return analytical_answer

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
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Retrieve semantically similar evidence and return only extractive source text."""
    analytical_answer = (
        _answer_ai_role_score(document, question)
        or _answer_ai_experience(document, question)
        or _answer_experience_duration(document, question, reference_date)
        or _answer_resume_projects(document, question)
        or _answer_resume_achievements(document, question)
    )
    if analytical_answer:
        return analytical_answer

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


def _answer_resume_projects(document: dict[str, Any], question: str) -> dict[str, Any] | None:
    if not PROJECT_QUESTION_RE.search(question):
        return None

    regions = _project_regions(document)
    if not regions:
        return _abstention(question, "I could not find project entries in this resume.")

    title_regions = [
        (page, region)
        for page, region in regions
        if region.get("type") not in {"list", "footer"}
        and not RESUME_LIST_MARKER_RE.match(region["text"].strip())
        and len(region["text"].strip()) <= 220
    ]
    project_names = [
        region["text"].split("|", 1)[0].strip().rstrip(":") for _, region in title_regions
    ]
    project_names = list(dict.fromkeys(name for name in project_names if name))
    if project_names:
        project_summary = (
            f"The resume lists {len(project_names)} project"
            f"{'s' if len(project_names) != 1 else ''}: {', '.join(project_names)}."
        )
    else:
        project_summary = "The resume includes project work described in the cited regions."

    citations = [
        {
            "id": f"citation-{index}",
            "page": page["number"],
            "bbox": region["bbox"],
            "region_id": region["id"],
            "quote": region["text"][:500],
            "score": 1.0,
        }
        for index, (page, region) in enumerate(regions[:10], start=1)
    ]
    return {
        "question": question,
        "answer": (
            f"{project_summary} The cited project title and accomplishment bullets describe what "
            "was built and the reported evaluation results."
        ),
        "grounded": True,
        "method": "resume-project-section-analysis",
        "citations": citations,
        "notice": "Project headings are excluded; citations point to project entries and their details.",
    }


def _answer_resume_achievements(document: dict[str, Any], question: str) -> dict[str, Any] | None:
    if not ACHIEVEMENT_QUESTION_RE.search(question):
        return None

    regions = _achievement_regions(document)
    if not regions:
        return _abstention(question, "I could not find achievement entries in this resume.")

    citations = [
        {
            "id": f"citation-{index}",
            "page": page["number"],
            "bbox": region["bbox"],
            "region_id": region["id"],
            "quote": region["text"][:500],
            "score": 1.0,
        }
        for index, (page, region) in enumerate(regions[:12], start=1)
    ]
    return {
        "question": question,
        "answer": (
            f"The resume contains {len(citations)} achievement, certification, or credential "
            f"entr{'y' if len(citations) == 1 else 'ies'}. Each complete entry is highlighted "
            "in the cited source regions."
        ),
        "grounded": True,
        "method": "resume-achievement-section-analysis",
        "citations": citations,
        "notice": "The section heading is excluded; citations point to the entries beneath it.",
    }


def _answer_ai_role_score(document: dict[str, Any], question: str) -> dict[str, Any] | None:
    if not AI_SCORE_QUESTION_RE.search(question):
        return None

    ai_answer = _answer_ai_experience(document, "Does the candidate have AI experience?")
    if not ai_answer or not ai_answer["grounded"]:
        return _abstention(question, "I could not verify enough AI evidence to produce a score.")

    experience_regions = _experience_regions(document)
    experience_text = "\n".join(region["text"] for _, region in experience_regions)
    document_text = "\n".join(
        region.get("text", "")
        for page in document.get("pages", [])
        for region in page.get("regions", [])
    )
    date_matches = list(DATE_RANGE_RE.finditer(experience_text))
    ai_role_count = sum(
        bool(
            AI_EVIDENCE_RE.search(
                experience_text[
                    match.end() : date_matches[index + 1].start()
                    if index + 1 < len(date_matches)
                    else len(experience_text)
                ]
            )
        )
        for index, match in enumerate(date_matches)
    )

    criteria = [
        (
            "LLM application engineering",
            1.5,
            1.5
            if re.search(
                r"\b(?:llms?|langchain|prompt optimization|model inference)\b",
                experience_text,
                re.IGNORECASE,
            )
            else 0,
        ),
        (
            "RAG and agentic systems",
            1.5,
            1.5
            if re.search(
                r"\b(?:rag|retrieval-augmented generation|multi-agent|ai agent)\b",
                experience_text,
                re.IGNORECASE,
            )
            else 0,
        ),
        (
            "document and multimodal AI",
            1.25,
            1.25
            if re.search(
                r"\b(?:document intelligence|docling|ocr|vlms?|vision-language)\b",
                experience_text,
                re.IGNORECASE,
            )
            else 0,
        ),
        (
            "production AI engineering",
            1.5,
            1.5
            if re.search(
                r"\b(?:cloud infrastructure|gcp|aws|pub/sub|production|\d[\d,]*\+ documents)\b",
                experience_text,
                re.IGNORECASE,
            )
            else 0,
        ),
        (
            "evaluation and reliability",
            1.0,
            1.0
            if re.search(
                r"\b(?:evaluated|ground-truth|accuracy|task-specific metrics|output normalization)\b",
                experience_text,
                re.IGNORECASE,
            )
            else 0,
        ),
    ]
    framework_evidence = bool(
        re.search(
            r"\b(?:pytorch|tensorflow|scikit-learn|machine learning|deep learning)\b",
            document_text,
            re.IGNORECASE,
        )
    )
    training_evidence = bool(
        re.search(
            r"\b(?:fine-tun(?:e|ed|ing)|trained? (?:a |the )?(?:model|network)|model training)\b",
            document_text,
            re.IGNORECASE,
        )
    )
    foundations_score = (0.5 if framework_evidence else 0) + (1.0 if training_evidence else 0)
    criteria.append(("ML and model-development depth", 1.5, min(1.5, foundations_score)))
    breadth_score = 0 if ai_role_count == 0 else min(1.25, 0.25 + ai_role_count * 0.25)
    criteria.append(("AI experience breadth", 1.25, breadth_score))
    ownership_score = (
        0.5
        if re.search(
            r"\b(?:founding engineer|architected|owning|owned|led)\b",
            experience_text,
            re.IGNORECASE,
        )
        else 0
    )
    criteria.append(("ownership", 0.5, ownership_score))
    score = round(sum(earned for _, _, earned in criteria), 2)

    citations = list(ai_answer["citations"])
    cited_regions = {citation["region_id"] for citation in citations}
    supporting_patterns = (
        re.compile(r"\b(?:evaluated|ground-truth|accuracy|task-specific metrics)\b", re.IGNORECASE),
        re.compile(r"\b(?:rag|retrieval-augmented generation)\b", re.IGNORECASE),
    )
    for pattern in supporting_patterns:
        for page, region in experience_regions:
            if region["id"] in cited_regions or not pattern.search(region["text"]):
                continue
            citations.append(
                {
                    "id": f"citation-{len(citations) + 1}",
                    "page": page["number"],
                    "bbox": region["bbox"],
                    "region_id": region["id"],
                    "quote": region["text"][:500],
                    "score": 1.0,
                }
            )
            cited_regions.add(region["id"])
            break

    breakdown = "; ".join(f"{label}: {earned:g}/{maximum:g}" for label, maximum, earned in criteria)
    gaps = []
    if not training_evidence:
        gaps.append("no explicit custom-model training or fine-tuning")
    if ai_role_count < 3:
        gaps.append("AI evidence spans only a limited number of dated roles")
    gap_text = "; ".join(gaps) if gaps else "no major résumé-evidence gaps in this rubric"
    return {
        "question": question,
        "answer": (
            f"Resume-only score: {score:g}/10 for an AI engineering role. {breakdown}. "
            f"Main limitations: {gap_text}. This score measures documented evidence, not interview performance."
        ),
        "grounded": True,
        "method": "resume-ai-role-rubric",
        "citations": citations,
        "notice": "The score uses a fixed evidence rubric and preserves citations for the supporting résumé claims.",
        "score": score,
        "score_max": 10,
        "rubric": [
            {"criterion": label, "earned": earned, "maximum": maximum}
            for label, maximum, earned in criteria
        ],
    }


def _answer_ai_experience(document: dict[str, Any], question: str) -> dict[str, Any] | None:
    if not AI_EXPERIENCE_QUESTION_RE.search(question):
        return None

    regions = _experience_regions(document)
    if not regions:
        return None

    combined_parts: list[str] = []
    offsets: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    cursor = 0
    for page, region in regions:
        text = region["text"].strip()
        offsets.append((cursor, page, region))
        combined_parts.append(text)
        cursor += len(text) + 1
    combined = "\n".join(combined_parts)
    role_dates = list(DATE_RANGE_RE.finditer(combined))

    by_role: dict[int, tuple[dict[str, Any], dict[str, Any], str]] = {}
    all_matches: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for index, (start, page, region) in enumerate(offsets):
        end = offsets[index + 1][0] - 1 if index + 1 < len(offsets) else len(combined)
        region_text = combined[start:end]
        match = AI_EVIDENCE_RE.search(region_text)
        if not match:
            continue
        sentence = _evidence_sentence(region_text, match.start())
        all_matches.append((page, region, sentence))
        global_position = start + match.start()
        role_index = sum(date_match.start() <= global_position for date_match in role_dates) - 1
        by_role.setdefault(max(0, role_index), (page, region, sentence))

    if not all_matches:
        return _abstention(
            question,
            "I found the Experience section, but no explicit AI, LLM, RAG, agent, or machine-learning evidence.",
        )

    representative_evidence = list(by_role.values()) if role_dates else all_matches[:3]
    capabilities = [label for pattern, label in AI_CAPABILITIES if pattern.search(combined)]
    if not capabilities:
        capabilities = ["artificial intelligence"]
    selected_region_ids = {region["id"] for _, region, _ in representative_evidence}
    for pattern, _ in AI_CAPABILITIES:
        if not pattern.search(combined) or any(
            pattern.search(sentence) for _, _, sentence in representative_evidence
        ):
            continue
        for page, region in regions:
            match = pattern.search(region["text"])
            if not match or region["id"] in selected_region_ids:
                continue
            representative_evidence.append(
                (page, region, _evidence_sentence(region["text"], match.start()))
            )
            selected_region_ids.add(region["id"])
            break
    dated_roles = [match.group(0) for index, match in enumerate(role_dates) if index in by_role]
    role_summary = (
        f" in {len(dated_roles)} dated roles ({'; '.join(dated_roles)})" if dated_roles else ""
    )
    capability_summary = ", ".join(capabilities[:-1])
    if len(capabilities) > 1:
        capability_summary += f", and {capabilities[-1]}"
    elif capabilities:
        capability_summary = capabilities[0]
    citations = [
        {
            "id": f"citation-{index}",
            "page": page["number"],
            "bbox": region["bbox"],
            "region_id": region["id"],
            "quote": sentence[:500],
            "score": 1.0,
        }
        for index, (page, region, sentence) in enumerate(representative_evidence, start=1)
    ]
    return {
        "question": question,
        "answer": (
            f"Yes. The resume documents AI-related professional work{role_summary}. "
            f"The cited evidence covers {capability_summary}."
        ),
        "grounded": True,
        "method": "resume-ai-experience-analysis",
        "citations": citations,
        "notice": "AI evidence is diversified across dated roles in the Experience section.",
    }


def _answer_experience_duration(
    document: dict[str, Any], question: str, reference_date: date | None
) -> dict[str, Any] | None:
    if not EXPERIENCE_QUESTION_RE.search(question):
        return None

    evidence: list[tuple[dict[str, Any], dict[str, Any], re.Match[str]]] = []
    today = reference_date or date.today()
    for page, region in _experience_regions(document):
        evidence.extend((page, region, match) for match in DATE_RANGE_RE.finditer(region["text"]))

    intervals: list[tuple[int, int]] = []
    for _, _, match in evidence:
        start = int(match["start_year"]) * 12 + MONTHS[match["start_month"].lower()] - 1
        if match["present"]:
            end = today.year * 12 + today.month - 1
        else:
            end = int(match["end_year"]) * 12 + MONTHS[match["end_month"].lower()] - 1
        if end >= start:
            intervals.append((start, end))

    if not intervals:
        return _abstention(
            question,
            "I found the experience section, but could not verify dated employment ranges.",
        )

    covered_months = set()
    for start, end in intervals:
        covered_months.update(range(start, end + 1))
    total_months = len(covered_months)
    years, months = divmod(total_months, 12)
    duration = _format_duration(years, months)
    range_labels = list(dict.fromkeys(match.group(0) for _, _, match in evidence))
    citations = [
        {
            "id": f"citation-{index}",
            "page": page["number"],
            "bbox": region["bbox"],
            "region_id": region["id"],
            "quote": match.group(0),
            "score": 1.0,
        }
        for index, (page, region, match) in enumerate(evidence, start=1)
    ]
    return {
        "question": question,
        "answer": (
            f"The resume shows approximately {duration} of professional experience across "
            f"{len(intervals)} dated role{'s' if len(intervals) != 1 else ''}: "
            f"{', '.join(range_labels)}. Overlapping months, if any, are counted only once."
        ),
        "grounded": True,
        "method": "resume-experience-date-analysis",
        "citations": citations,
        "notice": "The duration is calculated from month-level employment dates in the Experience section.",
    }


def _format_duration(years: int, months: int) -> str:
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    return " and ".join(parts) or "less than one month"


def _experience_regions(
    document: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    regions: list[tuple[dict[str, Any], dict[str, Any]]] = []
    in_experience = False
    for page in document.get("pages", []):
        for region in page.get("regions", []):
            if not region.get("text", "").strip():
                continue
            normalized = re.sub(r"[^a-z& ]", "", region["text"].lower()).strip()
            if normalized in EXPERIENCE_HEADINGS:
                in_experience = True
                continue
            if in_experience and normalized in SECTION_HEADINGS:
                return regions
            if in_experience:
                regions.append((page, region))
    return regions


def _project_regions(
    document: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    regions: list[tuple[dict[str, Any], dict[str, Any]]] = []
    in_projects = False
    for page in document.get("pages", []):
        for region in page.get("regions", []):
            if not region.get("text", "").strip():
                continue
            normalized = re.sub(r"[^a-z& ]", "", region["text"].lower()).strip()
            if normalized in PROJECT_HEADINGS:
                in_projects = True
                continue
            if in_projects and normalized in SECTION_HEADINGS:
                return regions
            if in_projects:
                regions.append((page, region))
    return regions


def _achievement_regions(
    document: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    regions: list[tuple[dict[str, Any], dict[str, Any]]] = []
    in_achievements = False
    for page in document.get("pages", []):
        for region in page.get("regions", []):
            if not region.get("text", "").strip():
                continue
            normalized = re.sub(r"[^a-z& ]", "", region["text"].lower()).strip()
            if normalized in ACHIEVEMENT_HEADINGS:
                in_achievements = True
                continue
            if in_achievements and normalized in SECTION_HEADINGS:
                return regions
            if in_achievements:
                regions.append((page, region))
    return regions


def _evidence_sentence(text: str, match_start: int) -> str:
    sentences = [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]
    if len(sentences) <= 1:
        return text.strip()
    cursor = 0
    for sentence in sentences:
        position = text.find(sentence, cursor)
        if position <= match_start < position + len(sentence):
            return sentence
        cursor = position + len(sentence)
    return text.strip()


def _abstention(question: str, message: str) -> dict[str, Any]:
    return {
        "question": question,
        "answer": message,
        "grounded": False,
        "method": "lexical-evidence-retrieval",
        "citations": [],
        "notice": "No answer was produced without supporting document evidence.",
    }
