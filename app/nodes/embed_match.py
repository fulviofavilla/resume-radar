"""
Node 3: embed_match
Performs semantic matching between the resume and job postings.

MVP:  LLM-extracted skills per job + keyword gap analysis.
      Uses both explicit and inferred resume skills for matching.
v2:   ChromaDB + OpenAI embeddings for full semantic similarity.
      The interface is identical — swap the implementation without touching the graph.
"""
import asyncio
import re
from collections import Counter
from app.models import AgentState, GapAnalysis
from app.nodes.parse_resume import extract_skills_from_job_description
import logging

logger = logging.getLogger(__name__)

# Words that appear in job postings but are NOT technical skills.
SKILL_NOISE = {
    "with", "and", "the", "for", "you", "will", "that", "have",
    "this", "our", "are", "your", "from", "they", "been", "work",
    "engineer", "engineering", "software", "technical", "support",
    "senior", "junior", "staff", "lead", "manager", "company",
    "team", "role", "experience", "skills", "working", "product",
    "more", "data", "system", "backend", "frontend", "front-end",
    "full", "stack", "build", "building", "using", "based", "able",
    "must", "strong", "good", "great", "also", "well", "help",
    "including", "across", "within", "between", "through", "about",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags before text processing."""
    return re.sub(r'<[^>]+>', ' ', text)


def _normalize(text: str) -> set[str]:
    """Lowercase, split, basic normalization."""
    return {w.strip(".,()") for w in text.lower().split()}


def _keyword_gap_analysis(
    resume_skills: list[str],
    job_postings_skills: list[list[str]],
    job_descriptions: list[str],
) -> GapAnalysis:
    """
    Gap analysis from resume skills vs LLM-extracted job skills.

    Uses the full resume skill set (explicit + inferred) passed in as resume_skills.

    Returns:
    - missing_skills: appear in ≥2 jobs but not in resume (real skills only)
    - keyword_gaps: domain terms frequent in descriptions but absent from resume
    - strengths: resume skills that appear frequently in job postings
    - match_score: % of top job skills covered by resume
    """
    resume_set = {s.lower() for s in resume_skills}

    # Aggregate all required skills across jobs (LLM-extracted — clean)
    all_job_skills: list[str] = []
    for skills in job_postings_skills:
        all_job_skills.extend([s.lower() for s in skills])

    job_skill_counts = Counter(all_job_skills)

    # Missing skills: in ≥2 jobs, not in resume, not noise
    missing_skills = [
        skill for skill, count in job_skill_counts.most_common(20)
        if skill not in resume_set
        and skill not in SKILL_NOISE
        and count >= 2
    ]

    # Keyword gaps: high-frequency terms in descriptions not in resume
    # Apply HTML strip before tokenizing to avoid tags polluting results
    all_desc_words: list[str] = []
    for desc in job_descriptions:
        all_desc_words.extend(_normalize(_strip_html(desc)))

    desc_word_counts = Counter(
        w for w in all_desc_words
        if len(w) > 3 and w not in SKILL_NOISE and not w.isdigit()
    )
    keyword_gaps = [
        word for word, count in desc_word_counts.most_common(30)
        if word not in resume_set and count >= 3
    ][:10]

    # Strengths: resume skills that appear in job postings
    strengths = [s for s in resume_skills if s.lower() in job_skill_counts]

    # Match score: % of top job skills covered by resume
    top_job_skills = {skill for skill, _ in job_skill_counts.most_common(20)}
    matched = resume_set.intersection(top_job_skills)
    match_score = len(matched) / len(top_job_skills) if top_job_skills else 0.0

    return GapAnalysis(
        missing_skills=missing_skills[:10],
        keyword_gaps=keyword_gaps,
        strengths=strengths,
        match_score=round(match_score, 2),
    )


async def embed_match_node(state: AgentState) -> AgentState:
    """
    LangGraph node: extracts real skills from job descriptions via LLM,
    then computes gap analysis against the resume profile (explicit + inferred skills).
    """
    if state.error:
        return state

    logger.info(f"[{state.job_id}] embed_match: extracting skills from {len(state.job_postings)} jobs")

    # Extract skills from all job descriptions in parallel via LLM
    extracted_skills_lists = await asyncio.gather(
        *[extract_skills_from_job_description(_strip_html(job.description))
        for job in state.job_postings]
    )

    # Replace noisy RemoteOK tags with clean LLM-extracted skills
    for job, skills in zip(state.job_postings, extracted_skills_lists):
        if skills:
            job.required_skills = skills
            logger.info(f"[{state.job_id}] embed_match: '{job.title[:40]}' → {skills}")

    # Combine explicit + inferred resume skills for a richer match
    explicit = state.resume_profile.skills if state.resume_profile else []
    inferred = state.resume_profile.inferred_skills if state.resume_profile else []
    all_resume_skills = explicit + inferred

    job_skills_lists = [job.required_skills for job in state.job_postings]
    job_descriptions = [job.description for job in state.job_postings]

    state.gap_analysis = _keyword_gap_analysis(
        resume_skills=all_resume_skills,
        job_postings_skills=job_skills_lists,
        job_descriptions=job_descriptions,
    )

    logger.info(
        f"[{state.job_id}] embed_match: match_score={state.gap_analysis.match_score}, "
        f"strengths={state.gap_analysis.strengths}, "
        f"missing={state.gap_analysis.missing_skills}"
    )
    return state
