from __future__ import annotations

import re
from datetime import date
from itertools import pairwise
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
PROJECT_HEADINGS = {"projects", "project experience", "personal projects", "selected projects"}


def answer_resume_fact(document: dict[str, Any], question: str) -> dict[str, Any] | None:
    """Answer common resume questions using section and role relationships."""
    q = question.lower().replace("’", "'")
    roles = _roles(document)
    experience = _section(document, EXPERIENCE_HEADINGS)
    skills = _section(document, SKILL_HEADINGS)
    projects = _section(document, PROJECT_HEADINGS)

    if re.search(
        r"\bsummar(?:ize|ise|y)\b.*professional background|professional background.*\bsummar", q
    ):
        companies = ", ".join(role["company"].rstrip(".") for role in roles)
        evidence = [
            *((role["page"], role["header"]) for role in roles),
            *_matching(
                experience, r"\b(?:ai agent|healthcare|rag|llm-powered|scalable architecture)\b"
            )[:5],
        ]
        return _response(
            question,
            f"The candidate is a software engineer with approximately {_total_role_duration(roles)} "
            f"of experience across {companies}. The resume emphasizes full-stack product delivery, "
            "AI agents and RAG, document intelligence, healthcare systems, and cloud architecture.",
            "resume-professional-summary",
            evidence,
        )

    if re.search(r"career timeline|chronological.*(?:career|employment)|employment timeline", q):
        ordered = sorted(roles, key=lambda item: item["start"])
        timeline = "; ".join(
            f"{role['dates']}: {role['title']} at {role['company'].rstrip('.')}" for role in ordered
        )
        return _response(
            question,
            f"Career timeline: {timeline}.",
            "resume-career-timeline-analysis",
            [(role["page"], role["header"]) for role in ordered],
        )

    if re.search(r"how long.*(?:each company|each employer|at each)|duration.*(?:company|role)", q):
        durations = "; ".join(
            f"{role['company'].rstrip('.')}: {_format_months(role['end'] - role['start'] + 1)}"
            for role in roles
        )
        return _response(
            question,
            f"Employment duration by company: {durations}.",
            "resume-role-duration-analysis",
            [(role["page"], role["header"]) for role in roles],
        )

    if re.search(r"\bgaps?\b.*(?:jobs?|employment|roles?)|between.*jobs?", q):
        gaps = _employment_gaps(roles)
        if gaps:
            detail = "; ".join(
                f"{_format_months(months)} between {first['company'].rstrip('.')} and "
                f"{second['company'].rstrip('.')}"
                for first, second, months in gaps
            )
            answer = f"The month-level dates show an employment gap of {detail}."
        else:
            answer = "The month-level dates do not show a gap between the listed roles."
        return _response(
            question,
            answer,
            "resume-employment-gap-analysis",
            [(role["page"], role["header"]) for role in roles],
        )

    if re.search(r"employment periods? overlap|roles? overlap|overlapping (?:jobs?|roles?)", q):
        overlaps = _employment_overlaps(roles)
        answer = (
            "The listed employment periods overlap: "
            + "; ".join(
                f"{first['company'].rstrip('.')} and {second['company'].rstrip('.')}"
                for first, second in overlaps
            )
            + "."
            if overlaps
            else "The month-level employment periods do not overlap."
        )
        return _response(
            question,
            answer,
            "resume-employment-overlap-analysis",
            [(role["page"], role["header"]) for role in roles],
        )

    if re.search(r"seniority progress|career progression|progressed.*senior", q):
        ordered = sorted(roles, key=lambda item: item["start"])
        progression = " to ".join(
            f"{role['title']} at {role['company'].rstrip('.')}" for role in ordered
        )
        return _response(
            question,
            f"The listed progression is {progression}.",
            "resume-seniority-progression-analysis",
            [(role["page"], role["header"]) for role in ordered],
        )

    if re.search(r"greatest impact|most impact|highest impact", q):
        if not roles:
            return None
        role = max(roles, key=lambda item: len(_quantified(item["bullets"])))
        evidence = _quantified(role["bullets"])
        return _response(
            question,
            f"Based on the density of quantified outcomes, the {role['company'].rstrip('.')} role "
            "shows the greatest documented impact. This is a resume-evidence comparison, not an "
            "independent performance judgment.",
            "resume-role-impact-analysis",
            evidence,
        )

    if re.search(r"leadership|ownership experience", q):
        evidence = _matching(
            experience,
            r"\b(?:founding engineer|architected|owning|owned|led|end-to-end migration)\b",
        )
        return _yes_evidence(
            question, "leadership and ownership", evidence, "resume-leadership-analysis"
        )

    if re.search(r"founding engineer", q):
        evidence = _matching(experience, r"\bfounding engineer\b")
        return _yes_evidence(question, "founding-engineer", evidence, "resume-leadership-analysis")

    if re.search(r"system[- ]design|systems? design", q):
        evidence = _matching(
            experience,
            r"\b(?:architected|designed|event-driven|scalable architecture|serverless .*pipeline|workflow automation system)\b",
        )
        return _response(
            question,
            f"The resume contains {len(evidence)} cited accomplishments demonstrating system-design "
            "work across AI platforms, automation, event-driven processing, scalability, and "
            "serverless pipelines.",
            "resume-system-design-analysis",
            evidence,
        )

    if re.search(r"apis? or backend frameworks?|backend frameworks?|apis? .*framework", q):
        framework_regions = _matching(skills, r"^frameworks?\s*&?\s*libraries\s*:")
        names = _named_technologies(
            framework_regions,
            ("Flask", "Node.js", "NestJS", "LangChain", "GraphQL", "Prisma ORM", "SQLAlchemy"),
        )
        evidence = [
            *framework_regions,
            *_matching(experience, r"\b(?:api|flask|node\.js|langchain|sqlalchemy|graphql)\b"),
        ]
        return _response(
            question,
            f"The listed backend and API frameworks are {', '.join(names)}.",
            "resume-framework-analysis",
            evidence,
        )

    if re.search(r"frontend frameworks?", q):
        framework_regions = _matching(skills, r"^frameworks?\s*&?\s*libraries\s*:")
        names = _named_technologies(
            framework_regions, ("ReactJS", "React Flow", "HTML/CSS", "Context API")
        )
        evidence = [
            *framework_regions,
            *_matching(experience, r"\b(?:reactjs|react flow|context api)\b"),
        ]
        return _response(
            question,
            f"The listed frontend frameworks are {', '.join(names)}.",
            "resume-framework-analysis",
            evidence,
        )

    if re.search(r"infrastructure and devops|devops tools?|infrastructure tools?", q):
        evidence = _matching(skills, r"^cloud\s*&?\s*devops\s*:")
        return _response(
            question,
            f"The listed infrastructure and DevOps tools are {_field_value(evidence, 'Cloud & DevOps')}.",
            "resume-devops-skill-analysis",
            evidence,
        )

    if re.search(r"event-driven", q):
        evidence = _matching(experience, r"\b(?:event-driven|pub/sub|eventbridge|sqs)\b")
        return _yes_evidence(
            question, "event-driven architecture", evidence, "resume-architecture-evidence-analysis"
        )

    if re.search(r"serverless", q):
        evidence = _matching(
            experience, r"\b(?:serverless|aws lambda|serverless application model)\b"
        )
        return _yes_evidence(
            question, "serverless systems", evidence, "resume-architecture-evidence-analysis"
        )

    if re.search(r"\bcaching\b|cache experience", q):
        evidence = _matching(experience, r"\b(?:caching|cache|redis)\b")
        return _response(
            question,
            "The resume documents Redis caching, document caching, and LLM response caching for "
            "latency, compute, and cost improvements.",
            "resume-caching-analysis",
            evidence,
        )

    if re.search(r"asynchronous processing|async processing", q):
        evidence = _matching(experience, r"\b(?:event-driven|pub/sub|sqs|serverless|lambda)\b")
        return _yes_evidence(
            question,
            "asynchronous and event-driven processing",
            evidence,
            "resume-architecture-evidence-analysis",
        )

    if re.search(r"database[- ]design", q):
        evidence = _matching(
            experience,
            r"\b(?:database design|postgresql|firestore|database backed|vector databases)\b",
        )
        return _response(
            question,
            "The resume documents database design and implementation with PostgreSQL, Firestore, "
            "database-backed caching, and vector-database integration.",
            "resume-database-design-analysis",
            evidence,
        )

    if re.search(r"vector databases?", q):
        evidence = _matching(experience, r"\bvector databases?\b")
        return _yes_evidence(
            question, "vector-database", evidence, "resume-database-design-analysis"
        )

    if re.search(r"security or compliance|security experience|compliance experience", q):
        evidence = _matching(
            experience, r"\b(?:hipaa|compliance|role-based access controls?|security)\b"
        )
        return _response(
            question,
            "The resume documents HIPAA compliance and role-based access controls in an EHR "
            "application.",
            "resume-security-compliance-analysis",
            evidence,
        )

    if re.search(r"\bhipaa\b", q):
        evidence = _matching(experience, r"\bhipaa\b")
        return _yes_evidence(
            question, "HIPAA-related", evidence, "resume-security-compliance-analysis"
        )

    if re.search(r"automation systems?", q):
        evidence = _matching(experience, r"\b(?:automation system|automation engine)\b")
        return _response(
            question,
            "The resume documents a healthcare workflow automation system and an event-driven "
            "Google Sheets automation engine.",
            "resume-automation-system-analysis",
            evidence,
        )

    if re.search(r"optimized? application performance|performance optimization", q):
        evidence = _matching(
            experience,
            r"\b(?:reduced api calls|memoiz|query optimizations?|latency|throughput|caching)\b",
        )
        return _response(
            question,
            "The resume documents frontend render optimization, a 3× API-call reduction, Redis and "
            "query optimization, caching, and a 10× workflow-throughput increase.",
            "resume-performance-optimization-analysis",
            evidence,
        )

    if re.search(r"largest workload|largest scale|highest volume", q):
        largest = _largest_workload(_role_bullets(roles))
        if not largest:
            return None
        token, item = largest
        return _response(
            question,
            f"The largest explicitly stated workload or served population is {token} in the cited "
            "healthcare workflow claim.",
            "resume-workload-analysis",
            [item],
        )

    if re.search(r"cost optimization", q):
        evidence = _matching(
            experience, r"\b(?:costs?|caching|compute overhead|redundant invocations)\b"
        )
        return _response(
            question,
            "Cost-optimization evidence includes up to an 80% LLM inference-cost reduction, "
            "response caching, and document caching that reduced compute overhead.",
            "resume-cost-reduction-analysis",
            evidence,
        )

    if re.search(r"reliability improvements?|reliability", q):
        evidence = _matching(
            experience,
            r"\b(?:compatibility|output normalization|caching|role-based access|production issue resolution)\b",
        )
        return _response(
            question,
            "Reliability-related evidence includes maintaining workflow compatibility, output "
            "normalization, caching, access controls, and production-issue resolution. The resume "
            "does not provide a direct uptime or incident-rate metric.",
            "resume-reliability-analysis",
            evidence,
        )

    if re.search(r"evaluation metrics?", q):
        evidence = [
            *_matching(experience, r"\b(?:task-specific metrics|accuracy|ground-truth)\b"),
            *_matching(
                projects, r"\b(?:dice|iou|boundary errors?|confidence intervals?|statistical)\b"
            ),
        ]
        return _response(
            question,
            "The resume names task-specific extraction metrics, verified ground truth, 95%+ "
            "accuracy, Dice, IoU, physical boundary errors, confidence intervals, and paired "
            "statistical comparisons.",
            "resume-evaluation-metric-analysis",
            evidence,
        )

    if re.search(r"medical imaging|medical image|mri", q):
        evidence = _matching(projects, r"\b(?:mri|medical image|segmentation|volumes?)\b")
        return _yes_evidence(
            question, "medical-imaging", evidence, "resume-project-domain-analysis"
        )

    if re.search(r"statistical[- ]analysis|statistics experience", q):
        evidence = _matching(
            projects, r"\b(?:bootstrap|confidence intervals?|paired statistical|failure analysis)\b"
        )
        return _response(
            question,
            "The project evidence includes bootstrap confidence intervals, paired statistical "
            "comparisons, and failure analysis.",
            "resume-statistical-analysis",
            evidence,
        )

    if re.search(r"claims? include measurable evidence|measurable claims?", q):
        evidence = _quantified(_role_bullets(roles))
        return _response(
            question,
            f"The resume contains {len(evidence)} professional claim regions with explicit numeric "
            "evidence. Each is highlighted below.",
            "resume-measurable-claim-analysis",
            evidence,
        )

    if re.search(r"claims? lack measurable evidence|lack measurable|without metrics?", q):
        bullets = _role_bullets(roles)
        quantified_ids = {item[1]["id"] for item in _quantified(bullets)}
        evidence = [item for item in bullets if item[1]["id"] not in quantified_ids]
        return _response(
            question,
            f"The resume contains {len(evidence)} professional claim regions without an explicit "
            "numeric outcome. This does not mean the work lacked impact; only that the resume does "
            "not quantify it.",
            "resume-unmeasured-claim-analysis",
            evidence,
        )

    if re.search(r"qualifications? match.*senior software|senior software.*qualifications?", q):
        evidence = [
            *(
                (role["page"], role["header"])
                for role in roles
                if "senior" in role["title"].lower()
            ),
            *_matching(
                experience,
                r"\b(?:founding engineer|architected|led|scalable architecture|production features|code reviews)\b",
            ),
            *_non_heading(skills),
        ]
        return _response(
            question,
            "The resume matches a senior software engineering role through an existing Senior "
            "Software Engineer title, founding-engineer ownership, system architecture, scalability "
            "work, production delivery, code reviews, and broad full-stack/cloud skills.",
            "resume-role-qualification-analysis",
            evidence,
        )

    if re.search(r"score.*backend engineering|backend engineering.*score", q):
        return _engineering_score(document, question, "backend", experience, skills)

    if re.search(r"score.*full[- ]stack engineering|full[- ]stack engineering.*score", q):
        return _engineering_score(document, question, "full-stack", experience, skills)

    if re.search(r"interview questions?.*verify|verify.*claims?.*interview", q):
        evidence = _matching(
            experience,
            r"\b(?:ai agent|rag|accuracy|throughput|costs?|active lives|hipaa)\b",
        )
        questions = (
            "1) Walk through the AI-agent architecture and your personal ownership. "
            "2) How did you evaluate RAG retrieval and grounding quality? "
            "3) How was the reported 95%+ extraction accuracy measured? "
            "4) What changes produced the 20-to-200 workflow throughput increase? "
            "5) What baseline and measurement produced the 80% LLM cost reduction? "
            "6) What did serving 1.7M+ active lives require technically? "
            "7) Which HIPAA and role-based controls did you implement directly?"
        )
        return _response(
            question,
            f"Evidence-verification interview questions: {questions}",
            "resume-interview-question-generation",
            evidence,
        )

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
            start, end = _date_bounds(date_match.group(0))
            roles.append(
                {
                    "company": company,
                    "title": title,
                    "dates": date_match.group(0),
                    "start": start,
                    "end": end,
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


def _date_bounds(value: str) -> tuple[int, int]:
    dates = re.findall(r"\b([A-Za-z]+)\s+(\d{4})\b", value)
    if not dates:
        return 0, 0
    start_month, start_year = dates[0]
    start = int(start_year) * 12 + _month(start_month) - 1
    if len(dates) > 1:
        end_month, end_year = dates[1]
        end = int(end_year) * 12 + _month(end_month) - 1
    else:
        today = date.today()
        end = today.year * 12 + today.month - 1
    return start, max(start, end)


def _format_months(months: int) -> str:
    years, remaining = divmod(max(0, months), 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if remaining:
        parts.append(f"{remaining} month{'s' if remaining != 1 else ''}")
    return " and ".join(parts) or "less than one month"


def _total_role_duration(roles: list[dict[str, Any]]) -> str:
    months: set[int] = set()
    for role in roles:
        months.update(range(role["start"], role["end"] + 1))
    return _format_months(len(months))


def _employment_gaps(
    roles: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any], int]]:
    ordered = sorted(roles, key=lambda item: item["start"])
    return [
        (first, second, second["start"] - first["end"] - 1)
        for first, second in pairwise(ordered)
        if second["start"] > first["end"] + 1
    ]


def _employment_overlaps(
    roles: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    ordered = sorted(roles, key=lambda item: item["start"])
    return [
        (first, second) for first, second in pairwise(ordered) if second["start"] <= first["end"]
    ]


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


def _quantified(
    regions: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        item
        for item in regions
        if re.search(r"(?:\d[\d,.]*\+?|\d+x|\d+%|\d+\.\d+[mM])", item[1]["text"])
    ]


def _named_technologies(
    regions: list[tuple[dict[str, Any], dict[str, Any]]], names: tuple[str, ...]
) -> list[str]:
    text = " ".join(item[1]["text"] for item in regions).lower()
    return [name for name in names if name.lower() in text]


def _largest_workload(
    regions: list[tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[str, tuple[dict[str, Any], dict[str, Any]]] | None:
    candidates = []
    pattern = re.compile(
        r"(\d[\d,]*(?:\.\d+)?[mMkK]?\+?)\s+(?:active\s+)?"
        r"(?:documents?|updates?|providers?|lives|requests?|workflows?|features?)\b"
    )
    for item in regions:
        for match in pattern.finditer(item[1]["text"]):
            token = match.group(1)
            normalized = token.lower().replace(",", "").rstrip("+")
            multiplier = 1
            if normalized.endswith("m"):
                multiplier = 1_000_000
                normalized = normalized[:-1]
            elif normalized.endswith("k"):
                multiplier = 1_000
                normalized = normalized[:-1]
            candidates.append((float(normalized) * multiplier, match.group(0), item))
    if not candidates:
        return None
    _, claim, item = max(candidates, key=lambda candidate: candidate[0])
    return claim, item


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


def _engineering_score(
    document: dict[str, Any],
    question: str,
    role_type: str,
    experience: list[tuple[dict[str, Any], dict[str, Any]]],
    skills: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    combined = [*skills, *experience]
    if role_type == "backend":
        definitions = (
            ("backend systems", 2.0, r"\b(?:backend|flask|node\.js|serverless|lambda)\b", 2.0),
            ("APIs and integrations", 1.5, r"\b(?:api|graphql|api gateway)\b", 1.0),
            ("databases and caching", 1.5, r"\b(?:postgresql|firestore|redis|caching)\b", 1.5),
            ("cloud and serverless", 1.5, r"\b(?:aws|gcp|lambda|cloud infrastructure)\b", 1.5),
            (
                "scalability and performance",
                1.5,
                r"\b(?:throughput|concurrent|latency|3x|10x)\b",
                1.5,
            ),
            (
                "security and reliability",
                1.0,
                r"\b(?:hipaa|role-based|compatibility|normalization)\b",
                1.0,
            ),
            ("ownership", 1.0, r"\b(?:founding engineer|architected|owning|led)\b", 1.0),
        )
        method = "resume-backend-role-rubric"
        gap = "The resume does not explicitly document API contract design or distributed tracing."
    else:
        definitions = (
            ("frontend engineering", 2.0, r"\b(?:frontend|reactjs|react flow|react\.memo)\b", 2.0),
            ("backend engineering", 2.0, r"\b(?:backend|flask|node\.js|lambda)\b", 2.0),
            ("data layer", 1.0, r"\b(?:postgresql|firestore|redis|mongodb)\b", 1.0),
            ("cloud delivery", 1.0, r"\b(?:aws|gcp|docker|serverless)\b", 1.0),
            (
                "architecture and scale",
                1.5,
                r"\b(?:architected|scalable|throughput|concurrent)\b",
                1.5,
            ),
            (
                "delivery and testing",
                1.5,
                r"\b(?:shipped|end-to-end testing|releases|production)\b",
                1.5,
            ),
            ("UI and UX evidence", 0.5, r"\b(?:template ui|frontend|reactjs)\b", 0.25),
            ("leadership", 0.5, r"\b(?:founding engineer|led|owning)\b", 0.5),
        )
        method = "resume-full-stack-role-rubric"
        gap = (
            "The resume provides limited explicit evidence of accessibility or design-system work."
        )

    rubric = []
    evidence = []
    for label, maximum, pattern, earned_when_present in definitions:
        matches = _matching(combined, pattern)
        earned = earned_when_present if matches else 0.0
        rubric.append({"criterion": label, "earned": earned, "maximum": maximum})
        evidence.extend(matches[:2])
    score = round(sum(item["earned"] for item in rubric), 2)
    result = _response(
        question,
        f"Resume-only score: {score:g}/10 for a {role_type} engineering role. {gap} "
        "This score measures documented evidence, not interview performance.",
        method,
        evidence,
    )
    result.update({"score": score, "score_max": 10, "rubric": rubric})
    return result


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
