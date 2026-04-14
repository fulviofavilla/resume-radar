"""
Node 1: parse_resume
Extracts text from the PDF and uses the LLM to structure the candidate's profile.
"""
import pdfplumber
import io
import json
from openai import AsyncOpenAI
from app.models import AgentState, ResumeProfile
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """
You are a resume parser. Extract structured information from the resume text below.

Return ONLY valid JSON matching this schema (no markdown, no explanation):
{{
  "skills": ["skill1", "skill2", ...],
  "seniority": "junior" | "mid" | "senior",
  "years_of_experience": <int or null>,
  "summary": "<2-3 sentence professional summary>"
}}

Rules:
- skills: technical skills only (languages, frameworks, tools, cloud platforms)
- seniority: infer from years of experience and job titles
- summary: written in third person, highlight strongest differentiators

Resume text:
---
{resume_text}
---
"""


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text from PDF bytes using pdfplumber."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


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
                    "content": EXTRACTION_PROMPT.format(resume_text=raw_text[:8000]),  # stay within context
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
        seniority=data.get("seniority", "mid"),
        years_of_experience=data.get("years_of_experience"),
        summary=data.get("summary", ""),
        raw_text=raw_text,
    )

    logger.info(
        f"[{state.job_id}] parse_resume: done — "
        f"{len(state.resume_profile.skills)} skills, "
        f"seniority={state.resume_profile.seniority}"
    )
    return state
