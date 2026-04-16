"""
Basic smoke tests for ResumeRadar.
Run with: pytest tests/ -v
"""
import pytest
from unittest.mock import AsyncMock, patch
from app.models import AgentState, ResumeProfile, JobPosting, GapAnalysis
from app.nodes.embed_match import _keyword_gap_analysis


# --- Unit tests (no API calls) ---

def test_keyword_gap_analysis_basic():
    resume_skills = ["python", "sql", "aws", "airflow"]
    job_skills = [
        ["python", "dbt", "kubernetes"],
        ["python", "terraform", "kubernetes"],
        ["sql", "dbt", "spark"],
    ]
    job_descriptions = [
        "We need python expertise with dbt and kubernetes experience",
        "Terraform and kubernetes required, python preferred",
        "Strong SQL and spark skills, dbt is a plus",
    ]

    result = _keyword_gap_analysis(resume_skills, job_skills, job_descriptions)

    assert "dbt" in result.missing_skills
    assert "kubernetes" in result.missing_skills
    assert "python" in result.strengths
    assert 0 <= result.match_score <= 1


def test_keyword_gap_analysis_perfect_match():
    skills = ["python", "sql", "aws"]
    job_skills = [["python", "sql", "aws"]] * 3
    job_descriptions = ["python sql aws"] * 3

    result = _keyword_gap_analysis(skills, job_skills, job_descriptions)

    assert result.match_score == 1.0
    assert result.missing_skills == []


def test_keyword_gap_analysis_no_match():
    resume_skills = ["cobol", "fortran"]
    job_skills = [["python", "rust", "go"]] * 3
    job_descriptions = ["python rust go developer"] * 3

    result = _keyword_gap_analysis(resume_skills, job_skills, job_descriptions)

    assert result.match_score == 0.0
    assert len(result.missing_skills) > 0


# --- Integration test (mocked OpenAI) ---

@pytest.mark.asyncio
async def test_parse_resume_node_mocked():
    """Ensure parse_resume_node correctly calls OpenAI and returns a ResumeProfile."""
    from app.nodes.parse_resume import parse_resume_node
    import json

    mock_response_content = json.dumps({
        "skills": ["Python", "SQL", "AWS"],
        "seniority": "mid",
        "years_of_experience": 3,
        "summary": "Data Engineer with Python and AWS expertise."
    })

    # Minimal valid PDF bytes (pdfplumber will fail, but we mock the text extraction)
    fake_state = AgentState(
        job_id="test-123",
        resume_bytes=b"fake-pdf-bytes",
    )

    with patch("app.nodes.parse_resume._extract_text_from_pdf", return_value="Python SQL AWS engineer 3 years"):
        with patch("openai.resources.chat.completions.AsyncCompletions.create") as mock_create:
            mock_create.return_value = AsyncMock(
                choices=[AsyncMock(message=AsyncMock(content=mock_response_content))]
            )
            result = await parse_resume_node(fake_state)

    assert result.resume_profile is not None
    assert "Python" in result.resume_profile.skills
    assert result.resume_profile.seniority == "mid"
    assert result.error is None


# --- rewrite_resume node tests ---

def _make_state_with_report():
    """Helper: build a fully populated AgentState for rewrite tests."""
    from app.models import Report, GapAnalysis

    profile = ResumeProfile(
        skills=["Python", "SQL", "AWS"],
        inferred_skills=["data modeling"],
        seniority="mid",
        years_of_experience=3,
        summary="Data engineer with Python and SQL experience.",
        raw_text="Data engineer with Python and SQL experience.\nBuilt pipelines.",
    )
    gaps = GapAnalysis(
        missing_skills=["dbt", "Kubernetes"],
        keyword_gaps=["orchestration"],
        strengths=["Python", "SQL"],
        match_score=0.72,
    )
    jobs = [
        JobPosting(
            title="Data Engineer",
            company="Acme",
            url="https://example.com",
            description="dbt, Kubernetes, Python required",
            required_skills=["dbt", "Kubernetes", "Python"],
            source="remoteok",
        )
    ]
    report = Report(
        gap_analysis=gaps,
        recommendations=["Learn dbt"],
        jobs_analyzed=1,
        top_jobs=jobs,
        resume_rewrites=[],
    )
    return AgentState(
        job_id="test-rewrite-456",
        resume_profile=profile,
        job_postings=jobs,
        gap_analysis=gaps,
        report=report,
    )


@pytest.mark.asyncio
async def test_rewrite_resume_node_populates_suggestions():
    """rewrite_resume_node should add RewriteSuggestions to report.resume_rewrites."""
    import json
    from app.nodes.rewrite_resume import rewrite_resume_node

    seg_response = json.dumps({
        "summary": "Data engineer with Python and SQL experience.",
        "bullets": [
            {"text": "Built pipelines.", "section": "Data Engineer at Acme"},
        ],
    })
    rw_response = json.dumps({
        "rewrites": [
            {
                "original": "Built pipelines.",
                "rewrite": "Designed and maintained production ETL pipelines in Python + Airflow, processing 10M+ daily events.",
                "reason": "Original lacks specificity and quantification.",
                "section": "Data Engineer at Acme",
                "alignment_note": "Incorporates 'Python' and 'data processing pipelines' — present in 3/5 top matching jobs.",
            }
        ]
    })

    state = _make_state_with_report()

    async def _fake_create(**kwargs):
        content = seg_response if "parser" in kwargs["messages"][0]["content"].lower() else rw_response
        return AsyncMock(choices=[AsyncMock(message=AsyncMock(content=content))])

    with patch("openai.resources.chat.completions.AsyncCompletions.create", side_effect=_fake_create):
        result = await rewrite_resume_node(state)

    assert result.report is not None
    assert len(result.report.resume_rewrites) >= 1
    rw = result.report.resume_rewrites[0]
    assert rw.original == "Built pipelines."
    assert "ETL" in rw.rewrite
    assert rw.section == "Data Engineer at Acme"
    assert "Python" in rw.alignment_note


def test_resolve_market_skills_uses_missing_skills_when_available():
    """Should prefer missing_skills over job required_skills."""
    from app.nodes.rewrite_resume import _resolve_market_skills
    from app.models import JobPosting

    jobs = [JobPosting(
        title="DE", company="X", url="http://x.com",
        description="", required_skills=["Spark"], source="remoteok"
    )]
    skills_str, source = _resolve_market_skills(["dbt", "Kafka"], jobs)

    assert "dbt" in skills_str
    assert "Kafka" in skills_str
    assert "Spark" not in skills_str
    assert "absent from your resume" in source


def test_resolve_market_skills_falls_back_to_job_skills():
    """When missing_skills is empty, should fall back to job required_skills."""
    from app.nodes.rewrite_resume import _resolve_market_skills
    from app.models import JobPosting

    jobs = [JobPosting(
        title="DE", company="X", url="http://x.com",
        description="", required_skills=["Spark", "dbt"], source="remoteok"
    )]
    skills_str, source = _resolve_market_skills([], jobs)

    assert "Spark" in skills_str
    assert "dbt" in skills_str
    assert "already covers" in source


@pytest.mark.asyncio
async def test_rewrite_resume_node_non_blocking_on_failure():
    """If LLM calls fail, the node should return state untouched (not raise)."""
    from app.nodes.rewrite_resume import rewrite_resume_node

    state = _make_state_with_report()

    with patch("openai.resources.chat.completions.AsyncCompletions.create", side_effect=Exception("API down")):
        result = await rewrite_resume_node(state)

    # Should not raise, should not set error, rewrites stays empty
    assert result.error is None
    assert result.report.resume_rewrites == []

