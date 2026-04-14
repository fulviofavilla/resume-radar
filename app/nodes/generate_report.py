"""
Node 4: generate_report
Uses the LLM to turn the gap analysis into actionable, human-readable recommendations.
"""
import json
from openai import AsyncOpenAI
from app.models import AgentState, Report
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

REPORT_PROMPT = """
You are a senior technical recruiter and career coach.

Given a candidate's profile and the gap analysis below, generate 5 specific, actionable recommendations.

Candidate profile:
- Skills: {skills}
- Demonstrated capabilities (inferred from experience): {inferred_skills}
- Seniority: {seniority}
- Summary: {summary}

Gap analysis:
- Missing skills (appear in job postings but not in resume): {missing_skills}
- Keyword gaps (domain terms frequent in jobs): {keyword_gaps}
- Strengths (resume skills valued by market): {strengths}
- Match score: {match_score} (0=no match, 1=perfect match)

Top job titles analyzed: {job_titles}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "recommendations": [
    "recommendation 1",
    "recommendation 2",
    "recommendation 3",
    "recommendation 4",
    "recommendation 5"
  ]
}}

Rules for recommendations:
- Be specific: name the skill, tool, or action
- Be honest: if the gap is critical, say so
- Be actionable: "Learn X" is bad. "Add X to your stack — it appears in 4/5 top matching jobs and unlocks $30-50/hr roles" is good
- Prioritize by market impact (what will most improve job match odds)
- One recommendation should highlight a strength to emphasize in their resume/interviews
"""


async def generate_report_node(state: AgentState) -> AgentState:
    """
    LangGraph node: generates the final report with LLM-powered recommendations.
    """
    if state.error:
        return state

    logger.info(f"[{state.job_id}] generate_report: starting")
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    profile = state.resume_profile
    gaps = state.gap_analysis
    jobs = state.job_postings

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": REPORT_PROMPT.format(
                        skills=", ".join(profile.skills),
                        inferred_skills=", ".join(profile.inferred_skills),
                        seniority=profile.seniority,
                        summary=profile.summary,
                        missing_skills=", ".join(gaps.missing_skills),
                        keyword_gaps=", ".join(gaps.keyword_gaps),
                        strengths=", ".join(gaps.strengths),
                        match_score=gaps.match_score,
                        job_titles=", ".join(j.title for j in jobs),
                    ),
                }
            ],
            temperature=0.3,
        )
        raw_json = response.choices[0].message.content.strip()
        data = json.loads(raw_json)
        recommendations = data.get("recommendations", [])
    except Exception as e:
        logger.warning(f"[{state.job_id}] generate_report: LLM failed, using fallback — {e}")
        # Fallback: generate basic recommendations without LLM
        recommendations = [
            f"Add {skill} to your stack — it appears frequently in matching job postings."
            for skill in gaps.missing_skills[:3]
        ] + [
            f"Your experience with {strength} is a strong market differentiator — highlight it prominently."
            for strength in gaps.strengths[:2]
        ]

    state.report = Report(
        gap_analysis=gaps,
        recommendations=recommendations,
        jobs_analyzed=len(jobs),
        top_jobs=jobs,
    )

    logger.info(f"[{state.job_id}] generate_report: done — {len(recommendations)} recommendations")
    return state
