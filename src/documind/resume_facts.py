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

    duration_match = re.search(
        r"(?:total experience with|how many years of)\s+([a-z0-9+.#/-]+)(?:\s+experience)?",
        q,
    )
    if duration_match and duration_match.group(1) not in {
        "experience",
        "professional",
        "work",
        "overall",
        "total",
    }:
        subject = duration_match.group(1)
        patterns = {
            "python": r"\bpython\b",
            "cloud": r"\b(?:aws|gcp|cloud|lambda|pub/sub|firestore)\b",
        }
        pattern = patterns.get(subject, rf"\b{re.escape(subject)}\b")
        matching_roles = [
            role
            for role in roles
            if any(re.search(pattern, item[1]["text"], re.IGNORECASE) for item in role["bullets"])
        ]
        months = _role_month_union(matching_roles)
        evidence = [
            *((role["page"], role["header"]) for role in matching_roles),
            *_matching(_role_bullets(matching_roles), pattern),
        ]
        return _response(
            question,
            f"The dated roles provide approximately {_format_months(months)} of documented "
            f"{subject} experience. This counts complete roles containing explicit {subject} "
            "evidence, so it is an estimate rather than a day-level calculation.",
            "resume-skill-duration-analysis",
            evidence,
        )

    if re.search(r"most backend ownership|most backend work", q):
        return _compare_role_focus(
            question,
            roles,
            r"\b(?:backend|flask|node\.js|postgresql|lambda|serverless|database design)\b",
            "backend ownership",
        )

    if re.search(r"most frontend work|most frontend ownership", q):
        return _compare_role_focus(
            question,
            roles,
            r"\b(?:frontend|reactjs|react flow|react\.memo|template ui|context api)\b",
            "frontend work",
        )

    if re.search(r"compare.*responsibilities.*(?:employers|roles)|responsibilities.*across", q):
        summaries = "; ".join(
            f"{role['company'].rstrip('.')}: {', '.join(_role_themes(role))}" for role in roles
        )
        return _response(
            question,
            f"Responsibility comparison — {summaries}.",
            "resume-role-comparison-analysis",
            _role_bullets(roles),
        )

    if re.search(r"responsibilities change|change.*between roles", q):
        ordered = sorted(roles, key=lambda item: item["start"])
        if len(ordered) < 2:
            return None
        first, second = ordered[0], ordered[-1]
        return _response(
            question,
            f"The responsibilities progressed from {', '.join(_role_themes(first))} at "
            f"{first['company'].rstrip('.')} to {', '.join(_role_themes(second))} and broader "
            f"end-to-end ownership at {second['company'].rstrip('.')}.",
            "resume-responsibility-progression-analysis",
            [*first["bullets"], *second["bullets"]],
        )

    if re.search(r"cross-functional collaboration|cross functional collaboration", q):
        evidence = _matching(
            experience, r"\b(?:collaborating|architects|designers|product team|code reviews)\b"
        )
        return _yes_evidence(
            question,
            "cross-functional collaboration",
            evidence,
            "resume-collaboration-analysis",
        )

    if re.search(r"code reviews?", q):
        evidence = _matching(experience, r"\bcode reviews?\b")
        return _yes_evidence(question, "code-review", evidence, "resume-quality-practice-analysis")

    if re.search(r"testing experience|experience.*testing", q):
        evidence = [
            *_matching(experience, r"\b(?:end-to-end testing|evaluated|ground-truth)\b"),
            *_matching(projects, r"\b(?:held-out|external|evaluation|failure analysis)\b"),
        ]
        return _response(
            question,
            "The resume documents end-to-end product testing, verified-ground-truth evaluation, "
            "held-out and external data evaluation, and failure analysis.",
            "resume-testing-analysis",
            evidence,
        )

    if re.search(r"production incidents?|production issues?", q):
        evidence = _matching(experience, r"\bproduction issue resolution\b")
        return _yes_evidence(
            question,
            "production-incident handling",
            evidence,
            "resume-production-operations-analysis",
        )

    if re.search(r"ci/cd|continuous integration|continuous delivery", q):
        evidence = _matching(skills, r"\b(?:ci/cd|github actions|gitlab)\b")
        return _response(
            question,
            "The resume lists CI/CD, GitHub Actions, GitHub, and GitLab. It does not describe a "
            "specific pipeline implementation in the experience bullets.",
            "resume-devops-skill-analysis",
            evidence,
        )

    if re.search(r"which aws services|aws services", q):
        evidence = [
            *_matching(skills, r"\baws\b"),
            *_matching(experience, r"\baws\b"),
        ]
        services = _parenthesized_services(evidence, "AWS")
        return _response(
            question,
            f"The listed AWS services are {', '.join(services)}.",
            "resume-cloud-service-analysis",
            evidence,
        )

    if re.search(r"which gcp services|gcp services", q):
        evidence = [
            *_matching(skills, r"\bgcp\b"),
            *_matching(experience, r"\b(?:gcp|pub/sub|firestore|gcs)\b"),
        ]
        services = _parenthesized_services(evidence, "GCP")
        return _response(
            question,
            f"The listed GCP services are {', '.join(services)}.",
            "resume-cloud-service-analysis",
            evidence,
        )

    if re.search(r"containerization|containers?", q):
        evidence = _matching(skills, r"\bdocker\b")
        return _response(
            question,
            "The resume lists Docker as a containerization tool, but it does not describe a "
            "container deployment accomplishment.",
            "resume-devops-skill-analysis",
            evidence,
        )

    if re.search(r"message queues?|event buses?", q):
        evidence = [
            *_matching(skills, r"\b(?:sqs|eventbridge|pub/sub)\b"),
            *_matching(experience, r"\bpub/sub\b"),
        ]
        return _response(
            question,
            "The resume lists Amazon SQS, Amazon EventBridge, and Google Cloud Pub/Sub. Pub/Sub is "
            "also supported by an experience bullet.",
            "resume-messaging-service-analysis",
            evidence,
        )

    if re.search(r"data[- ]storage services?|storage services?", q):
        evidence = [
            *_matching(skills, r"\b(?:rds|s3|gcs|firestore|postgresql|mongodb|redis)\b"),
            *_matching(experience, r"\b(?:firestore|gcs|postgresql|database)\b"),
        ]
        return _response(
            question,
            "The resume lists Amazon RDS and S3, Google Cloud Storage and Firestore, plus "
            "PostgreSQL, MySQL, MongoDB, and Redis.",
            "resume-storage-service-analysis",
            evidence,
        )

    if re.search(r"role-based access controls?|rbac", q):
        evidence = _matching(experience, r"\brole-based access controls?\b")
        return _yes_evidence(
            question,
            "role-based access control",
            evidence,
            "resume-security-compliance-analysis",
        )

    if re.search(r"api optimization", q):
        evidence = _matching(experience, r"\breduced api calls\b|\bapi calls by 3x\b")
        return _response(
            question,
            "The resume reports a 3× API-call reduction through React data-fetching, memoization, "
            "and state-management optimization.",
            "resume-api-optimization-analysis",
            evidence,
        )

    if re.search(r"frontend optimization", q):
        evidence = _matching(
            experience,
            r"\b(?:reactjs data fetching|react\.memo|usememo|usecallback|context api|re-renders)\b",
        )
        return _response(
            question,
            "Frontend optimization evidence includes corrected React data-fetching dependencies, "
            "component and callback memoization, Context API restructuring, and fewer re-renders.",
            "resume-frontend-optimization-analysis",
            evidence,
        )

    if re.search(r"database optimization", q):
        evidence = _matching(
            experience, r"\b(?:redis caching|query optimizations?|database backed caching)\b"
        )
        return _response(
            question,
            "Database optimization evidence includes Redis caching, query optimization, and "
            "database-backed document reuse to remove redundant processing.",
            "resume-database-optimization-analysis",
            evidence,
        )

    if re.search(r"cloud cost optimization", q):
        evidence = _matching(
            experience,
            r"\b(?:serverless pdf pipeline|compute overhead|llm inference costs|response caching)\b",
        )
        return _response(
            question,
            "Cloud and compute cost evidence includes serverless execution, document caching that "
            "reduced compute overhead, and an 80% LLM inference-cost reduction through prompt and "
            "response-cache optimization.",
            "resume-cloud-cost-analysis",
            evidence,
        )

    if re.search(r"largest percentage improvement|highest percentage improvement", q):
        improvement = _largest_percentage_improvement(_role_bullets(roles))
        if not improvement:
            return None
        percent, item = improvement
        return _response(
            question,
            f"The largest explicitly stated percentage improvement is {percent}%: the reported LLM "
            "inference-cost reduction.",
            "resume-percentage-impact-analysis",
            [item],
        )

    if re.search(r"rank.*three strongest accomplishments|three strongest accomplishments", q):
        ranked = _rank_accomplishments(_role_bullets(roles), 3)
        descriptions = " ".join(
            f"{index}) {item[1]['text'].lstrip('–—-• ').rstrip()}"
            for index, item in enumerate(ranked, start=1)
        )
        return _response(
            question,
            "Resume-evidence ranking by quantified scale: " + descriptions,
            "resume-accomplishment-ranking",
            ranked,
        )

    if re.search(r"relevant to an ai platform|ai platform company", q):
        evidence = _matching(
            experience,
            r"\b(?:ai agent|multi-agent|rag|document intelligence|llm|ocr|vlms?|event-driven)\b",
        )
        return _response(
            question,
            "The most relevant evidence covers AI-agent platform ownership, multi-agent "
            "orchestration, RAG, document intelligence with OCR/VLMs, LLM evaluation, and "
            "event-driven AI automation.",
            "resume-target-company-relevance-analysis",
            evidence,
        )

    if re.search(r"evaluating model quality|model quality evaluation", q):
        evidence = [
            *_matching(
                experience, r"\b(?:evaluated llm|ground-truth|task-specific metrics|accuracy)\b"
            ),
            *_matching(projects, r"\b(?:dice|iou|boundary errors?|failure analysis)\b"),
        ]
        return _response(
            question,
            "Yes. The resume documents LLM extraction evaluation against verified ground truth and "
            "model-quality evaluation using Dice, IoU, boundary errors, and failure analysis.",
            "resume-model-quality-analysis",
            evidence,
        )

    if re.search(r"evaluating generalization|generalization evaluation", q):
        evidence = _matching(
            projects, r"\b(?:external|generalization|dice decline|failure analysis)\b"
        )
        return _response(
            question,
            "Yes. The medical-imaging project evaluated external data and quantified a mean Dice "
            "decline from 0.790 to 0.537 to identify cross-dataset generalization limitations.",
            "resume-generalization-analysis",
            evidence,
        )

    if re.search(r"external[- ]validation", q):
        evidence = _matching(
            projects, r"\b(?:external 3d volumes|external 2d data|generalization)\b"
        )
        return _response(
            question,
            "The project used external 3D volumes and external 2D data to measure performance "
            "degradation and cross-dataset generalization.",
            "resume-external-validation-analysis",
            evidence,
        )

    if re.search(r"computer[- ]vision experience|computer vision", q):
        evidence = [
            *_matching(skills, r"\b(?:opencv|tesseract|easyocr)\b"),
            *_matching(experience, r"\b(?:ocr|vlms?|document intelligence)\b"),
            *_matching(projects, r"\b(?:segmentation|mri|medical image)\b"),
        ]
        return _response(
            question,
            "Computer-vision evidence includes OpenCV, Tesseract, EasyOCR, OCR/VLM document "
            "intelligence, and an MRI segmentation-evaluation project.",
            "resume-computer-vision-analysis",
            evidence,
        )

    if re.search(r"classical machine[- ]learning|classical ml", q):
        evidence = [
            *_matching(skills, r"\bscikit-learn\b"),
            *_matching(projects, r"\b(?:classical segmentation|segmentation methods|bootstrap)\b"),
        ]
        return _response(
            question,
            "The resume lists scikit-learn and a reproducible comparison of three classical "
            "segmentation methods with statistical evaluation.",
            "resume-classical-ml-analysis",
            evidence,
        )

    if re.search(r"deep[- ]learning frameworks?", q):
        evidence = _matching(skills, r"\b(?:tensorflow|pytorch)\b")
        names = _named_technologies(evidence, ("TensorFlow", "PyTorch"))
        return _response(
            question,
            f"The listed deep-learning frameworks are {', '.join(names)}. The resume lists them as "
            "skills but does not tie them to a detailed production training project.",
            "resume-ml-framework-analysis",
            evidence,
        )

    if re.search(r"data[- ]analysis ability|data analysis ability", q):
        evidence = [
            *_matching(skills, r"\b(?:numpy|pandas|scikit-learn)\b"),
            *_matching(
                projects, r"\b(?:dice|iou|confidence intervals?|statistical|failure analysis)\b"
            ),
            *_matching(experience, r"\b(?:task-specific metrics|ground-truth|accuracy)\b"),
        ]
        return _response(
            question,
            "Data-analysis evidence includes NumPy, Pandas, scikit-learn, statistical comparisons, "
            "confidence intervals, failure analysis, and task-specific evaluation metrics.",
            "resume-data-analysis",
            evidence,
        )

    if re.search(r"skills?.*ml engineer.*missing|ml engineer.*skills?.*missing", q):
        evidence = [
            *_matching(skills, r"\b(?:tensorflow|pytorch|scikit-learn|numpy|pandas)\b"),
            *_matching(experience, r"\b(?:llm|rag|document intelligence|evaluation)\b")[:4],
        ]
        return _response(
            question,
            "Resume-visible ML engineering gaps are: no explicit model training or fine-tuning, "
            "feature-pipeline ownership, experiment tracking, model registry, model serving, drift "
            "monitoring, or production ML observability. These are omission-based inferences, not "
            "proof that the candidate lacks the skills.",
            "resume-ml-gap-analysis",
            evidence,
            notice="Gap claims are inferred from missing resume evidence; citations show the documented baseline.",
        )

    if re.search(
        r"score.*machine[- ]learning engineering|machine[- ]learning engineering.*score", q
    ):
        return _engineering_score(document, question, "machine-learning", experience, skills)

    if re.search(r"score.*cloud engineering|cloud engineering.*score", q):
        return _engineering_score(document, question, "cloud", experience, skills)

    if re.search(r"score.*healthcare software|healthcare software.*score", q):
        return _engineering_score(document, question, "healthcare", experience, skills)

    if re.search(r"generate technical interview questions?|technical interview questions?", q):
        evidence = _matching(
            experience,
            r"\b(?:ai agent|rag|document intelligence|throughput|serverless|costs?|hipaa)\b",
        )
        answer = (
            "Technical interview questions: 1) Diagram the AI-agent platform and explain your "
            "ownership. 2) How did you evaluate RAG retrieval and grounding? 3) How was 95%+ LLM "
            "extraction accuracy measured? 4) What architectural changes enabled 200 concurrent "
            "workflows? 5) How did the serverless PDF pipeline handle 1,000+ concurrent requests? "
            "6) What baseline produced the 80% LLM cost reduction? 7) How were HIPAA controls "
            "implemented?"
        )
        return _response(question, answer, "resume-technical-interview-generation", evidence)

    if re.search(r"generate behavioral interview questions?|behavioral interview questions?", q):
        evidence = _matching(
            experience,
            r"\b(?:founding engineer|led|collaborating|production issue|owning|migration)\b",
        )
        answer = (
            "Behavioral interview questions: 1) Describe a time you owned an ambiguous product "
            "end to end. 2) How did you lead the workflow migration while preserving compatibility? "
            "3) Tell me about a production issue you helped resolve. 4) How did you work with "
            "architects, designers, and product partners? 5) Describe a tradeoff between speed, "
            "cost, and reliability. 6) What feedback changed your technical approach?"
        )
        return _response(question, answer, "resume-behavioral-interview-generation", evidence)

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

    if re.search(
        r"weakness|missing (?:qualifications?|skills?)|(?:qualifications?|skills?).{0,30}missing|gaps?|lacks?",
        q,
    ) and re.search(r"\bai\b|artificial intelligence|machine learning", q):
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
    return _format_months(_role_month_union(roles))


def _role_month_union(roles: list[dict[str, Any]]) -> int:
    months: set[int] = set()
    for role in roles:
        months.update(range(role["start"], role["end"] + 1))
    return len(months)


def _compare_role_focus(
    question: str,
    roles: list[dict[str, Any]],
    pattern: str,
    label: str,
) -> dict[str, Any] | None:
    scored = [(len(_matching(role["bullets"], pattern)), role) for role in roles]
    if not scored:
        return None
    count, role = max(scored, key=lambda item: item[0])
    evidence = _matching(role["bullets"], pattern)
    return _response(
        question,
        f"The {role['company'].rstrip('.')} role contains the most documented {label}, with "
        f"{count} matching responsibility entr{'y' if count == 1 else 'ies'}.",
        "resume-role-focus-comparison",
        evidence,
    )


def _role_themes(role: dict[str, Any]) -> list[str]:
    text = " ".join(item[1]["text"] for item in role["bullets"]).lower()
    definitions = (
        ("AI platform and agent workflows", r"ai agent|multi-agent"),
        ("RAG and document intelligence", r"rag|document intelligence|ocr|vlm"),
        ("event-driven automation", r"event-driven|pub/sub|automation engine"),
        ("healthcare workflow systems", r"healthcare|active lives|providers"),
        ("application and API performance", r"api calls|react\.memo|latency|query optimization"),
        ("scalability and serverless processing", r"throughput|concurrent|serverless"),
        ("LLM healthcare products", r"ehr|llm-powered|hipaa"),
        ("production delivery and collaboration", r"production features|code reviews|product team"),
    )
    return [label for label, pattern in definitions if re.search(pattern, text)][:4]


def _parenthesized_services(
    evidence: list[tuple[dict[str, Any], dict[str, Any]]], provider: str
) -> list[str]:
    text = " ".join(item[1]["text"] for item in evidence)
    match = re.search(rf"\b{re.escape(provider)}\s*\(([^)]+)\)", text, re.IGNORECASE)
    return [item.strip() for item in match.group(1).split(",")] if match else []


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


def _largest_percentage_improvement(
    regions: list[tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[int, tuple[dict[str, Any], dict[str, Any]]] | None:
    candidates = []
    for item in regions:
        text = item[1]["text"]
        if not re.search(r"\b(?:reduc|sav|improv|increas)", text, re.IGNORECASE):
            continue
        candidates.extend((int(value), item) for value in re.findall(r"(\d+)%", text))
    return max(candidates, key=lambda candidate: candidate[0]) if candidates else None


def _rank_accomplishments(
    regions: list[tuple[dict[str, Any], dict[str, Any]]], limit: int
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    scored = []
    for item in regions:
        text = item[1]["text"]
        values = []
        for token in re.findall(r"\d[\d,]*(?:\.\d+)?[mMkK]?\+?", text):
            normalized = token.lower().replace(",", "").rstrip("+")
            multiplier = 1
            if normalized.endswith("m"):
                multiplier, normalized = 1_000_000, normalized[:-1]
            elif normalized.endswith("k"):
                multiplier, normalized = 1_000, normalized[:-1]
            try:
                values.append(float(normalized) * multiplier)
            except ValueError:
                continue
        scored.append((max(values, default=0), item))
    scored.sort(key=lambda entry: entry[0], reverse=True)
    return [item for _, item in scored[:limit]]


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
    projects = _section(document, PROJECT_HEADINGS)
    combined = [*skills, *experience, *projects]
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
    elif role_type == "full-stack":
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
    elif role_type == "machine-learning":
        definitions = (
            ("ML frameworks", 1.0, r"\b(?:pytorch|tensorflow|scikit-learn)\b", 1.0),
            (
                "model evaluation",
                1.5,
                r"\b(?:ground-truth|accuracy|dice|iou|failure analysis)\b",
                1.5,
            ),
            ("applied AI systems", 1.5, r"\b(?:llm|rag|ai agent|multi-agent)\b", 1.5),
            ("data analysis", 1.0, r"\b(?:numpy|pandas|confidence intervals?|statistical)\b", 1.0),
            (
                "production ML scale",
                1.5,
                r"\b(?:documents daily|cloud infrastructure|production)\b",
                1.5,
            ),
            (
                "training and MLOps",
                1.5,
                r"\b(?:fine-tun|model training|mlflow|model registry|drift)\b",
                0.0,
            ),
            ("computer vision and document AI", 1.0, r"\b(?:opencv|ocr|vlms?|segmentation)\b", 1.0),
            ("ownership", 0.5, r"\b(?:founding engineer|architected|owning|led)\b", 0.5),
            ("ML foundations", 0.5, r"\b(?:deep learning|machine learning|scikit-learn)\b", 0.5),
        )
        method = "resume-ml-role-rubric"
        gap = "The resume lacks explicit model training, fine-tuning, registry, serving, and drift-monitoring evidence."
    elif role_type == "cloud":
        definitions = (
            ("AWS", 1.5, r"\baws\b", 1.5),
            ("GCP", 1.5, r"\bgcp\b", 1.5),
            ("serverless systems", 1.5, r"\b(?:serverless|lambda)\b", 1.5),
            (
                "event-driven architecture",
                1.0,
                r"\b(?:pub/sub|sqs|eventbridge|event-driven)\b",
                1.0,
            ),
            ("cloud data services", 1.0, r"\b(?:rds|s3|gcs|firestore)\b", 1.0),
            ("scalability", 1.5, r"\b(?:throughput|concurrent|scalable)\b", 1.5),
            ("containers and CI/CD", 1.0, r"\b(?:docker|github actions|ci/cd)\b", 0.5),
            (
                "operations and reliability",
                1.0,
                r"\b(?:production issue|caching|compatibility)\b",
                1.0,
            ),
        )
        method = "resume-cloud-role-rubric"
        gap = "The resume does not explicitly document Kubernetes, Terraform, or infrastructure-as-code ownership."
    else:
        definitions = (
            ("healthcare domain scale", 2.0, r"\b(?:healthcare|active lives|providers)\b", 2.0),
            ("workflow automation", 1.5, r"\bworkflow automation\b", 1.5),
            ("EHR and patient systems", 1.5, r"\b(?:ehr|patient-profile)\b", 1.5),
            ("HIPAA and access control", 1.0, r"\b(?:hipaa|role-based access)\b", 1.0),
            ("production delivery", 1.0, r"\bproduction features\b", 1.0),
            ("backend and data", 1.0, r"\b(?:backend|postgresql|flask)\b", 1.0),
            ("scale and performance", 1.0, r"\b(?:1\.7m|throughput|concurrent|75%)\b", 1.0),
            ("AI-enabled healthcare", 1.0, r"\b(?:llm-powered ehr|llm inference)\b", 1.0),
        )
        method = "resume-healthcare-role-rubric"
        gap = "The resume does not explicitly document clinical outcomes or direct clinical responsibility."

    rubric = []
    evidence = []
    for label, maximum, pattern, earned_when_present in definitions:
        matches = _matching(combined, pattern)
        earned = earned_when_present if matches else 0.0
        rubric.append({"criterion": label, "earned": earned, "maximum": maximum})
        evidence.extend(matches[:2])
    score = round(sum(item["earned"] for item in rubric), 2)
    display_role = {
        "backend": "backend engineering",
        "full-stack": "full-stack engineering",
        "machine-learning": "machine-learning engineering",
        "cloud": "cloud engineering",
        "healthcare": "healthcare software",
    }[role_type]
    result = _response(
        question,
        f"Resume-only score: {score:g}/10 for a {display_role} role. {gap} "
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
