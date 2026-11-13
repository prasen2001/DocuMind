from documind.qa import answer_question


def _resume() -> dict:
    regions = []

    def add(text: str, region_type: str = "paragraph") -> None:
        index = len(regions) + 1
        regions.append(
            {
                "id": f"region-{index}",
                "type": region_type,
                "bbox": [10, index * 10, 500, index * 10 + 8],
                "text": text,
            }
        )

    add("Education", "heading")
    add("Example University | MS in Computer Science | Aug 2026 – Dec 2028")
    add("Example Institute | BE in Electronics Engineering | Aug 2019 – Jun 2023")
    add("Technical Skills", "heading")
    add("Languages: Python, TypeScript, JavaScript, Java, C++, SQL")
    add("Frameworks & Libraries: ReactJS, Flask, LangChain, TensorFlow, PyTorch, Scikit-learn")
    add("Databases: PostgreSQL, MySQL, MongoDB, Firestore, Redis")
    add("Cloud & DevOps: AWS, GCP, Nebius, Docker, GitHub Actions")
    add("Experience", "heading")
    add("Alpha AI | Remote Senior Software Engineer | Sep 2025 – Aug 2026")
    add(
        "– Founding Engineer who architected an AI Agent platform, owning frontend, backend, AI "
        "workflows, and GCP cloud infrastructure.",
        "list",
    )
    add("– Implemented multi-agent orchestration for AI workflows.", "list")
    add(
        "– Built retrieval-augmented generation (RAG) pipelines integrating document processing "
        "and vector databases.",
        "list",
    )
    add(
        "– Developed an LLM document intelligence pipeline using Docling, OCR, and VLMs, processing "
        "1,000+ documents daily; evaluated extraction against ground-truth examples with "
        "task-specific metrics and 95%+ accuracy.",
        "list",
    )
    add(
        "– Engineered an event-driven automation engine processing 10,000+ updates with GCP "
        "Pub/Sub.",
        "list",
    )
    add("Beta Health Inc. | Pune, India Software Engineer | Jul 2023 – Jun 2025")
    add(
        "– Designed a workflow automation system for 200+ healthcare providers and 1.7M+ active "
        "lives, saving 75% time with AWS and PostgreSQL.",
        "list",
    )
    add("– Reduced API calls by 3x through ReactJS optimization and caching.", "list")
    add(
        "– Led migration to a scalable architecture, increasing throughput from 20 to 200 "
        "concurrent workflows (10x).",
        "list",
    )
    add(
        "– Built a serverless PDF pipeline on AWS Lambda supporting 1,000+ concurrent requests "
        "with caching that reduced compute overhead.",
        "list",
    )
    add(
        "– Architected an LLM-powered EHR synopsis with Flask, LangChain, PostgreSQL, patient "
        "integration, HIPAA controls, and backend ownership.",
        "list",
    )
    add(
        "– Reduced LLM inference costs by 80% through prompt optimization and response caching; "
        "implemented output normalization for frontend consumption.",
        "list",
    )
    add("– Built and shipped 50+ production healthcare features.", "list")
    add("Projects", "heading")
    add("Medical Image Segmentation Evaluator | Python, NumPy | GitHub")
    add("– Built a reproducible evaluation pipeline for 500+ images.", "list")
    add("– Measured Dice, IoU, confidence intervals, and failures.", "list")
    add("Achievements & Certifications", "heading")
    add("• National engineering competition rank 6.", "list")
    return {
        "id": "resume-suite",
        "filename": "resume.pdf",
        "pages": [{"number": 1, "regions": regions}],
    }


QUESTIONS = [
    (
        "How many years of professional experience does the candidate have?",
        "resume-experience-date-analysis",
        "3 years",
    ),
    (
        "Does the candidate have AI engineering experience?",
        "resume-ai-experience-analysis",
        "2 dated roles",
    ),
    ("Score the candidate out of 10 for an AI engineering role.", "resume-ai-role-rubric", "/10"),
    (
        "What evidence supports the candidate’s AI experience?",
        "resume-ai-experience-analysis",
        "AI-related",
    ),
    ("Which companies has the candidate worked for?", "resume-employer-analysis", "Alpha AI"),
    (
        "What was the candidate’s most recent position?",
        "resume-chronology-analysis",
        "Senior Software Engineer",
    ),
    (
        "What were the candidate’s responsibilities at Beta Health?",
        "resume-role-responsibility-analysis",
        "7 responsibility",
    ),
    (
        "What did the candidate build at Alpha AI?",
        "resume-role-build-analysis",
        "build or delivery",
    ),
    ("Has the candidate worked with LLMs?", "resume-ai-experience-analysis", "LLM applications"),
    (
        "Does the candidate have RAG experience?",
        "resume-technical-evidence-analysis",
        "RAG experience",
    ),
    (
        "Has the candidate built multi-agent systems?",
        "resume-technical-evidence-analysis",
        "multi-agent systems",
    ),
    (
        "What document-intelligence experience does the candidate have?",
        "resume-technical-evidence-analysis",
        "document intelligence",
    ),
    (
        "Has the candidate worked with OCR or vision-language models?",
        "resume-technical-evidence-analysis",
        "vision-language",
    ),
    (
        "What AI evaluation methods has the candidate used?",
        "resume-ai-evaluation-analysis",
        "ground truth",
    ),
    (
        "Has the candidate deployed AI systems in production?",
        "resume-production-ai-analysis",
        "production-scale",
    ),
    (
        "What measurable results did the candidate achieve?",
        "resume-quantified-results-analysis",
        "quantified",
    ),
    (
        "What are the candidate’s strongest technical skills?",
        "resume-skill-section-analysis",
        "Languages",
    ),
    (
        "Which programming languages does the candidate know?",
        "resume-skill-section-analysis",
        "Python",
    ),
    ("What cloud platforms has the candidate used?", "resume-cloud-skill-analysis", "AWS"),
    ("Does the candidate have AWS experience?", "resume-cloud-skill-analysis", "AWS experience"),
    ("Does the candidate have GCP experience?", "resume-cloud-skill-analysis", "GCP experience"),
    (
        "What databases has the candidate worked with?",
        "resume-skill-section-analysis",
        "PostgreSQL",
    ),
    (
        "Does the candidate have frontend development experience?",
        "resume-domain-experience-analysis",
        "frontend development",
    ),
    (
        "Does the candidate have backend development experience?",
        "resume-domain-experience-analysis",
        "backend development",
    ),
    (
        "What healthcare technology experience does the candidate have?",
        "resume-healthcare-experience-analysis",
        "healthcare workflow",
    ),
    (
        "What scalability improvements has the candidate delivered?",
        "resume-scalability-analysis",
        "10×",
    ),
    ("What cost reductions has the candidate achieved?", "resume-cost-reduction-analysis", "80%"),
    (
        "What is the candidate’s educational background?",
        "resume-education-section-analysis",
        "Master of Science",
    ),
    (
        "What projects has the candidate completed?",
        "resume-project-section-analysis",
        "Medical Image Segmentation",
    ),
    (
        "What weaknesses or missing qualifications are visible for an AI engineering role?",
        "resume-gap-analysis",
        "fine-tuning",
    ),
]


def test_all_thirty_resume_questions_have_grounded_non_heading_evidence() -> None:
    document = _resume()
    bare_headings = {
        "education",
        "technical skills",
        "experience",
        "projects",
        "achievements & certifications",
    }

    for question, expected_method, answer_fragment in QUESTIONS:
        result = answer_question(document, question)

        assert result["method"] == expected_method, question
        assert result["grounded"] is True, question
        assert result["citations"], question
        assert answer_fragment.lower() in result["answer"].lower(), question
        assert all(
            citation["quote"].strip().lower() not in bare_headings
            for citation in result["citations"]
        ), question


ADDITIONAL_QUESTIONS = [
    (
        "Summarize the candidate’s professional background.",
        "resume-professional-summary",
        "3 years",
    ),
    (
        "Create a chronological career timeline.",
        "resume-career-timeline-analysis",
        "Career timeline",
    ),
    ("How long did the candidate work at each company?", "resume-role-duration-analysis", "1 year"),
    ("Are there gaps between the candidate’s jobs?", "resume-employment-gap-analysis", "2 months"),
    ("Did any employment periods overlap?", "resume-employment-overlap-analysis", "do not overlap"),
    (
        "How has the candidate’s seniority progressed?",
        "resume-seniority-progression-analysis",
        "Senior Software Engineer",
    ),
    (
        "Which role appears to have had the greatest impact?",
        "resume-role-impact-analysis",
        "greatest documented impact",
    ),
    (
        "What leadership or ownership experience is documented?",
        "resume-leadership-analysis",
        "leadership and ownership",
    ),
    (
        "Has the candidate worked as a founding engineer?",
        "resume-leadership-analysis",
        "founding-engineer",
    ),
    (
        "Which accomplishments demonstrate system-design ability?",
        "resume-system-design-analysis",
        "system-design",
    ),
    (
        "What APIs or backend frameworks has the candidate used?",
        "resume-framework-analysis",
        "Flask",
    ),
    ("What frontend frameworks has the candidate used?", "resume-framework-analysis", "ReactJS"),
    ("What infrastructure and DevOps tools are listed?", "resume-devops-skill-analysis", "AWS"),
    (
        "Does the candidate have event-driven architecture experience?",
        "resume-architecture-evidence-analysis",
        "event-driven",
    ),
    (
        "Has the candidate built serverless systems?",
        "resume-architecture-evidence-analysis",
        "serverless",
    ),
    (
        "What caching experience does the candidate have?",
        "resume-caching-analysis",
        "response caching",
    ),
    (
        "Has the candidate designed asynchronous processing systems?",
        "resume-architecture-evidence-analysis",
        "asynchronous",
    ),
    (
        "What evidence demonstrates database-design experience?",
        "resume-database-design-analysis",
        "database design",
    ),
    (
        "Has the candidate worked with vector databases?",
        "resume-database-design-analysis",
        "vector-database",
    ),
    (
        "What security or compliance experience is documented?",
        "resume-security-compliance-analysis",
        "HIPAA",
    ),
    (
        "Does the candidate have HIPAA experience?",
        "resume-security-compliance-analysis",
        "HIPAA-related",
    ),
    (
        "What automation systems has the candidate built?",
        "resume-automation-system-analysis",
        "automation system",
    ),
    (
        "Has the candidate optimized application performance?",
        "resume-performance-optimization-analysis",
        "3×",
    ),
    (
        "What is the largest workload the candidate has handled?",
        "resume-workload-analysis",
        "1.7M+ active lives",
    ),
    (
        "Which accomplishments demonstrate cost optimization?",
        "resume-cost-reduction-analysis",
        "80%",
    ),
    (
        "Which accomplishments demonstrate reliability improvements?",
        "resume-reliability-analysis",
        "Reliability-related",
    ),
    (
        "What experience does the candidate have with evaluation metrics?",
        "resume-evaluation-metric-analysis",
        "Dice",
    ),
    (
        "Has the candidate worked with medical imaging?",
        "resume-project-domain-analysis",
        "medical-imaging",
    ),
    (
        "What statistical-analysis experience is documented?",
        "resume-statistical-analysis",
        "confidence intervals",
    ),
    (
        "Which claims include measurable evidence?",
        "resume-measurable-claim-analysis",
        "numeric evidence",
    ),
    (
        "Which résumé claims lack measurable evidence?",
        "resume-unmeasured-claim-analysis",
        "without an explicit",
    ),
    (
        "What qualifications match a senior software engineering role?",
        "resume-role-qualification-analysis",
        "Senior Software Engineer",
    ),
    ("Score the candidate for a backend engineering role.", "resume-backend-role-rubric", "/10"),
    (
        "Score the candidate for a full-stack engineering role.",
        "resume-full-stack-role-rubric",
        "/10",
    ),
    (
        "What interview questions should be asked to verify the candidate’s claims?",
        "resume-interview-question-generation",
        "Walk through",
    ),
]


def test_all_thirty_five_additional_questions_have_relevant_evidence() -> None:
    document = _resume()
    bare_headings = {
        "education",
        "technical skills",
        "experience",
        "projects",
        "achievements & certifications",
    }

    for question, expected_method, answer_fragment in ADDITIONAL_QUESTIONS:
        result = answer_question(document, question)

        assert result["method"] == expected_method, question
        assert result["grounded"] is True, question
        assert result["citations"], question
        assert answer_fragment.lower() in result["answer"].lower(), question
        assert all(
            citation["quote"].strip().lower() not in bare_headings
            for citation in result["citations"]
        ), question
        if expected_method.endswith("role-rubric"):
            assert 0 <= result["score"] <= result["score_max"] == 10, question
