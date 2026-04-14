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
