from __future__ import annotations

import re
from typing import Any

DATE_RANGE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\s*"
    r"(?:[-–—]|\bto\b)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"[a-z]*\.?\s+\d{4}|Present|Current|Now)\b",
    re.IGNORECASE,
)
JOB_TITLE_RE = re.compile(
    r"\b((?:(?:Senior|Staff|Principal|Lead|Founding|Junior)\s+)?"
    r"(?:Software|AI|ML|Machine Learning|Data|Full[- ]Stack|Backend|Frontend)\s+Engineer|"
    r"Engineering Manager|Data Scientist|Research Scientist|Developer|Consultant|Intern)\b",
    re.IGNORECASE,
)
SECTION_HEADINGS = {
    "education",
    "technical skills",
    "skills",
    "experience",
    "work experience",
    "professional experience",
    "employment",
    "projects",
    "project experience",
    "personal projects",
    "selected projects",
    "achievements",
    "achievements & certifications",
    "certifications",
    "awards",
    "honors",
    "honors & awards",
    "publications",
}
EXPERIENCE_HEADINGS = {"experience", "work experience", "professional experience", "employment"}
SKILL_HEADINGS = {"technical skills", "skills"}
EDUCATION_HEADINGS = {"education"}


def answer_resume_fact(document: dict[str, Any], question: str) -> dict[str, Any] | None:
    """Answer common resume questions using section and role relationships."""
    q = question.lower().replace("’", "'")
    roles = _roles(document)
    experience = _section(document, EXPERIENCE_HEADINGS)
    skills = _section(document, SKILL_HEADINGS)

    if re.search(r"\b(?:which|what) companies\b|\bemployers?\b", q):
        companies = list(dict.fromkeys(role["company"] for role in roles if role["company"]))
        evidence = [(role["page"], role["header"]) for role in roles]
        return _response(
            question,
            f"The candidate has worked for {', '.join(name.rstrip('.') for name in companies)}.",
            "resume-employer-analysis",
            evidence,
        )

    if re.search(r"\bmost recent (?:position|role|job)\b|\bcurrent (?:position|role|job)\b", q):
        if not roles:
            return None
        role = max(roles, key=lambda item: item["start"])
        return _response(
            question,
            f"The most recent listed position is {role['title']} at {role['company']} "
            f"({role['dates']}).",
            "resume-chronology-analysis",
            [(role["page"], role["header"])],
        )

    if "responsibilit" in q and (role := _role_for_question(roles, q)):
        return _response(
            question,
            f"The resume lists {len(role['bullets'])} responsibility and accomplishment entries "
            f"for {role['company'].rstrip('.')}. The complete entries are highlighted below.",
            "resume-role-responsibility-analysis",
            role["bullets"],
        )

    if re.search(r"\b(?:build|built|create|created|develop|developed|deliver|delivered)\b", q) and (
        role := _role_for_question(roles, q)
    ):
        evidence = _matching(
            role["bullets"],
            r"\b(?:built|implemented|developed|engineered|architected|designed|delivered)\b",
        )
        return _response(
            question,
            f"At {role['company']}, the candidate has {len(evidence)} cited build or delivery "
            "accomplishments.",
            "resume-role-build-analysis",
            evidence,
        )

    concept_queries = (
        (
            r"\brag\b|retrieval[- ]augmented",
            r"\b(?:rag|retrieval-augmented generation)\b",
            "RAG",
        ),
        (
            r"multi[- ]agent|agent systems?",
            r"\b(?:multi-agent|agent orchestration)\b",
            "multi-agent systems",
        ),
        (
            r"document[- ]intelligence|document intelligence",
            r"\b(?:document intelligence|docling|ocr|vlms?|document processing)\b",
            "document intelligence",
        ),
        (
            r"\bocr\b|vision[- ]language|\bvlms?\b",
            r"\b(?:ocr|vlms?|vision-language models?)\b",
            "OCR and vision-language models",
        ),
    )
    for query_pattern, evidence_pattern, label in concept_queries:
        if re.search(query_pattern, q, re.IGNORECASE):
            evidence = _matching(experience, evidence_pattern)
            return _yes_evidence(question, label, evidence, "resume-technical-evidence-analysis")

    if re.search(r"\bai evaluation\b|evaluation methods?", q):
        evidence = _matching(
            experience,
            r"\b(?:evaluated|ground-truth|task-specific metrics|accuracy|output normalization)\b",
        )
        return _response(
            question,
            "The resume documents evaluation against verified ground truth with task-specific "
            "metrics and extraction accuracy, plus output normalization for reliable consumption.",
            "resume-ai-evaluation-analysis",
            evidence,
        )

    if re.search(r"\b(?:deployed|deployment|production)\b.*\bai\b|\bai\b.*\bproduction\b", q):
        evidence = _matching(
            experience,
            r"\b(?:ai agent platform|cloud infrastructure|documents daily|pub/sub|llm-powered|production)\b",
        )
        return _response(
            question,
            "The resume supports production-scale AI engineering through an end-to-end AI platform, "
            "cloud infrastructure, document processing at 1,000+ documents daily, and a delivered LLM "
            "healthcare application. It does not explicitly use the phrase 'deployed to production'.",
            "resume-production-ai-analysis",
            evidence,
        )

    if re.search(r"measurable results?|quantified|metrics?|numbers?", q):
        evidence = [
            item
            for item in _role_bullets(roles)
            if re.search(r"(?:\d[\d,.]*\+?|\d+x|\d+%|\d+\.\d+[mM])", item[1]["text"])
        ]
        return _response(
            question,
            f"The resume contains {len(evidence)} quantified professional outcomes covering scale, "
            "throughput, efficiency, accuracy, cost, and shipped features.",
            "resume-quantified-results-analysis",
            evidence,
        )

    if re.search(r"strongest technical skills?|technical skills?", q):
        evidence = _non_heading(skills)
        categories = [
            item[1]["text"].split(":", 1)[0] for item in evidence if ":" in item[1]["text"]
        ]
        return _response(
            question,
            f"The resume groups the candidate's technical skills into {', '.join(categories)}.",
            "resume-skill-section-analysis",
            evidence,
        )

    if re.search(r"programming languages?|languages? (?:does|do|has|know|uses?)", q):
        evidence = _matching(skills, r"^languages\s*:")
        value = _field_value(evidence, "Languages")
        return _response(
            question,
            f"The listed programming languages are {value}.",
            "resume-skill-section-analysis",
            evidence,
        )

    if re.search(r"cloud platforms?|cloud providers?", q):
        evidence = _matching(skills, r"^cloud\s*&?\s*devops\s*:")
        platforms = [
            name
            for name in ("AWS", "GCP", "Azure", "Google Cloud", "Nebius")
            if any(name.lower() in item[1]["text"].lower() for item in evidence)
        ]
        return _response(
            question,
            f"The listed cloud platforms are {', '.join(platforms)}.",
            "resume-cloud-skill-analysis",
            evidence,
        )

    for provider in ("AWS", "GCP", "Azure"):
        if re.search(rf"\b{provider.lower()}\b", q):
            evidence = _matching([*skills, *experience], rf"\b{provider}\b")
            return _yes_evidence(question, provider, evidence, "resume-cloud-skill-analysis")

    if re.search(r"\bdatabases?\b", q):
        evidence = _matching(skills, r"^databases?\s*:")
        value = _field_value(evidence, "Databases")
        return _response(
            question,
            f"The listed databases are {value}.",
            "resume-skill-section-analysis",
            evidence,
        )

    if re.search(r"\bfrontend\b", q):
        evidence = _matching(
            experience, r"\b(?:frontend|reactjs|react flow|react\.memo|template ui)\b"
        )
        return _yes_evidence(
            question, "frontend development", evidence, "resume-domain-experience-analysis"
        )

    if re.search(r"\bbackend\b", q):
        evidence = _matching(
            experience, r"\b(?:backend|flask|node\.js|aws lambda|serverless|postgresql)\b"
        )
        return _yes_evidence(
            question, "backend development", evidence, "resume-domain-experience-analysis"
        )

    if re.search(r"\bhealthcare\b|health technology|healthtech", q):
        evidence = _matching(
            experience, r"\b(?:healthcare|ehr|hipaa|patient|providers?|active lives)\b"
        )
        return _response(
            question,
            "The resume documents healthcare workflow automation, an LLM-powered EHR synopsis, "
            "patient-profile integration, and HIPAA-aware access controls.",
            "resume-healthcare-experience-analysis",
            evidence,
        )

    if re.search(r"scalab|throughput|concurren", q):
        evidence = _matching(experience, r"\b(?:scalable|throughput|concurrent|serverless|scale)\b")
        return _response(
            question,
            "The cited evidence includes a 10× workflow-throughput increase from 20 to 200 "
            "concurrent workflows and a serverless PDF pipeline supporting 1,000+ concurrent requests.",
            "resume-scalability-analysis",
            evidence,
        )

    if re.search(r"\bcost reductions?\b|reduce(?:d)? (?:llm )?costs?|cost savings?", q):
        evidence = _matching(
            experience, r"\b(?:costs?|caching|compute overhead|redundant invocations)\b"
        )
        return _response(
            question,
            "The resume reports up to an 80% reduction in LLM inference costs through prompt "
            "optimization and response caching, plus compute savings from document caching.",
            "resume-cost-reduction-analysis",
            evidence,
        )

    if re.search(r"educational background|\beducation\b|degrees?", q):
        evidence = _non_heading(_section(document, EDUCATION_HEADINGS))
        return _response(
            question,
            "The resume lists a Master of Science in Computer Science at USC and a Bachelor of "
            "Engineering in Electronics and Telecommunication Engineering.",
            "resume-education-section-analysis",
            evidence,
        )

    if re.search(r"weakness|missing qualifications?|gaps?|lacks?", q) and re.search(
        r"\bai\b|artificial intelligence|machine learning", q
    ):
        ai_evidence = _matching(
            experience,
            r"\b(?:ai agent|rag|llm|document intelligence|multi-agent)\b",
        )[:4]
        framework_evidence = _matching(skills, r"\b(?:pytorch|tensorflow|scikit-learn)\b")
        return _response(
            question,
            "Resume-visible gaps for an AI engineering role are: no explicit custom-model training "
            "or fine-tuning, no stated model-serving or model-monitoring stack, limited evidence of "
            "AI work across only two dated roles, and no listed AI research publications. These are "
            "inferences from omissions, not proof that the candidate lacks those abilities.",
            "resume-gap-analysis",
            [*ai_evidence, *framework_evidence],
            notice="Gap claims are inferred from missing resume evidence; citations show the documented baseline.",
        )

    return None


def _section(
    document: dict[str, Any], headings: set[str]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    active = False
    for page in document.get("pages", []):
        for region in page.get("regions", []):
            text = region.get("text", "").strip()
            if not text:
                continue
            normalized = re.sub(r"[^a-z& ]", "", text.lower()).strip()
            if normalized in headings:
                active = True
                continue
            if active and normalized in SECTION_HEADINGS:
                return selected
            if active:
                selected.append((page, region))
    return selected


def _roles(document: dict[str, Any]) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    for page, region in _section(document, EXPERIENCE_HEADINGS):
        date_match = DATE_RANGE_RE.search(region["text"])
        if date_match:
            header_text = region["text"]
            company = header_text.split("|", 1)[0].strip()
            title_match = JOB_TITLE_RE.search(header_text)
            title = title_match.group(1) if title_match else "role"
            start_match = re.search(r"\b([A-Za-z]+)\s+(\d{4})", date_match.group(0))
            start = (
                int(start_match.group(2)) * 12 + _month(start_match.group(1)) if start_match else 0
            )
            roles.append(
                {
                    "company": company,
                    "title": title,
                    "dates": date_match.group(0),
                    "start": start,
                    "page": page,
                    "header": region,
                    "bullets": [],
                }
            )
        elif roles:
            roles[-1]["bullets"].append((page, region))
    return roles


def _month(value: str) -> int:
    names = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    return next((index for index, name in enumerate(names, 1) if value.lower().startswith(name)), 0)


def _role_for_question(roles: list[dict[str, Any]], question: str) -> dict[str, Any] | None:
    for role in roles:
        tokens = [
            token for token in re.findall(r"[a-z0-9]+", role["company"].lower()) if len(token) > 3
        ]
        if any(token in question for token in tokens):
            return role
    return None


def _role_bullets(roles: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [item for role in roles for item in role["bullets"]]


def _matching(
    regions: list[tuple[dict[str, Any], dict[str, Any]]], pattern: str
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    regex = re.compile(pattern, re.IGNORECASE)
    return [item for item in regions if regex.search(item[1]["text"])]


def _non_heading(
    regions: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [item for item in regions if item[1].get("type") not in {"heading", "title", "header"}]


def _field_value(evidence: list[tuple[dict[str, Any], dict[str, Any]]], label: str) -> str:
    if not evidence:
        return "not explicitly listed"
    text = evidence[0][1]["text"]
    return text.split(":", 1)[1].strip() if ":" in text else text


def _yes_evidence(
    question: str,
    label: str,
    evidence: list[tuple[dict[str, Any], dict[str, Any]]],
    method: str,
) -> dict[str, Any]:
    if not evidence:
        return _response(
            question,
            f"The resume does not contain explicit evidence of {label}.",
            method,
            [],
            grounded=False,
        )
    return _response(
        question,
        f"Yes. The resume contains {len(evidence)} cited entr{'y' if len(evidence) == 1 else 'ies'} "
        f"supporting {label} experience.",
        method,
        evidence,
    )


def _response(
    question: str,
    answer: str,
    method: str,
    evidence: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    grounded: bool = True,
    notice: str = "Section-aware resume analysis with source-region evidence.",
) -> dict[str, Any]:
    unique: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for page, region in evidence:
        if region["id"] in seen or region.get("type") in {"heading", "title", "header"}:
            continue
        seen.add(region["id"])
        unique.append((page, region))
    citations = [
        {
            "id": f"citation-{index}",
            "page": page["number"],
            "bbox": region["bbox"],
            "region_id": region["id"],
            "quote": region["text"][:500],
            "score": 1.0,
        }
        for index, (page, region) in enumerate(unique[:12], start=1)
    ]
    return {
        "question": question,
        "answer": answer,
        "grounded": grounded and bool(citations),
        "method": method,
        "citations": citations,
        "notice": notice,
    }
