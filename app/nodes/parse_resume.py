"""
Node 1: parse_resume
Extracts text from the PDF and uses the LLM to structure the candidate's profile.

Also exposes extract_skills_from_job_description() used by embed_match
to get real skills from job postings (instead of relying on RemoteOK tags).
"""
import pdfplumber
import io
import json
from openai import AsyncOpenAI
from app.models import AgentState, ResumeProfile
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

# ── Resume extraction prompt ──────────────────────────────────────────────────

EXTRACTION_PROMPT = """
You are a resume parser that mimics how modern AI-powered ATS systems analyze candidates.

Extract structured information from the resume text below — consider the ENTIRE document,
not just the Skills section. Infer skills demonstrated in job descriptions and projects.

Return ONLY valid JSON matching this schema (no markdown, no explanation):
{{
  "skills": ["skill1", "skill2", ...],
  "inferred_skills": ["skill1", "skill2", ...],
  "seniority": "junior" | "mid" | "senior",
  "years_of_experience": <int or null>,
  "summary": "<2-3 sentence professional summary>"
}}

Rules:
- skills: explicitly listed technical skills (languages, frameworks, tools, cloud platforms)
- inferred_skills: skills DEMONSTRATED in job descriptions/projects but NOT explicitly listed
  Examples: "built ETL pipelines at scale" → ["distributed systems", "data modeling"]
            "reduced storage by 90% migrating to AWS" → ["AWS S3", "cost optimization", "data migration"]
            "CI/CD workflows for data pipelines" → ["CI/CD", "pipeline automation"]
- seniority: infer from years of experience and job titles
- summary: written in third person, highlight strongest differentiators

Resume text:
---
{resume_text}
---
"""

# ── Job description skill extraction prompt ───────────────────────────────────

JOB_SKILL_PROMPT = """
Extract only the required and preferred technical skills from this job description.
Include: programming languages, frameworks, tools, platforms, databases, cloud services.
Exclude: soft skills, generic words (e.g. "communication", "teamwork", "experience").

Return ONLY a JSON array of strings. No markdown, no explanation.
Example: ["Python", "AWS", "dbt", "Airflow", "PostgreSQL"]

Job description:
---
{description}
---
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text from PDF bytes using pdfplumber."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


async def extract_skills_from_job_description(description: str) -> list[str]:
    """
    Use the LLM to extract real technical skills from a job description.
    Called by embed_match_node to get accurate required_skills per job.

    Returns an empty list on failure (non-blocking).
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": JOB_SKILL_PROMPT.format(
                        description=description[:3000]  # cap to avoid token bloat
                    ),
                }
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        # Strip accidental markdown fences if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        skills = json.loads(raw)
        if isinstance(skills, list):
            return [s for s in skills if isinstance(s, str)]
    except Exception as e:
        logger.warning(f"extract_skills_from_job_description failed: {e}")

    return []


# ── Node ──────────────────────────────────────────────────────────────────────

async def parse_resume_node(state: AgentState) -> AgentState:
    """
    LangGraph node: parses the PDF and extracts a structured ResumeProfile.
    """
    logger.info(f"[{state.job_id}] parse_resume: starting")
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Step 1: Extract raw text from PDF
    try:
        raw_text = _extract_text_from_pdf(state.resume_bytes)
        if not raw_text.strip():
            state.error = "Could not extract text from PDF. Make sure the file is not scanned/image-only."
            return state
    except Exception as e:
        state.error = f"PDF parsing failed: {str(e)}"
        return state

    logger.info(f"[{state.job_id}] parse_resume: extracted {len(raw_text)} chars from PDF")

    # Step 2: LLM structured extraction
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(resume_text=raw_text[:8000]),
                }
            ],
            temperature=0,
        )
        raw_json = response.choices[0].message.content.strip()
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        state.error = f"LLM returned malformed JSON during resume parsing: {str(e)}"
        return state
    except Exception as e:
        state.error = f"LLM call failed during resume parsing: {str(e)}"
        return state

    state.resume_profile = ResumeProfile(
        skills=data.get("skills", []),
        inferred_skills=data.get("inferred_skills", []),  # ← was missing
        seniority=data.get("seniority", "mid"),
        years_of_experience=data.get("years_of_experience"),
        summary=data.get("summary", ""),
        raw_text=raw_text,
    )

    logger.info(
        f"[{state.job_id}] parse_resume: done — "
        f"{len(state.resume_profile.skills)} explicit skills, "
        f"{len(state.resume_profile.inferred_skills)} inferred skills, "
        f"seniority={state.resume_profile.seniority}"
    )
    return state
