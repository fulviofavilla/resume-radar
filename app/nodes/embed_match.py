"""
Node 3: embed_match
Performs semantic matching between the resume and job postings.

MVP: keyword-based overlap (fast, no infra needed).
v2:  ChromaDB + OpenAI embeddings for true semantic similarity.
     The interface is the same — swap the implementation without touching the graph.
"""
from app.models import AgentState, GapAnalysis
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


def _normalize(text: str) -> set[str]:
    """Lowercase, split, basic normalization."""
    return {w.strip(".,()") for w in text.lower().split()}


def _keyword_gap_analysis(
    resume_skills: list[str],
    job_postings_skills: list[list[str]],
    job_descriptions: list[str],
) -> GapAnalysis:
    """
    MVP gap analysis: set operations on skills + keyword frequency in descriptions.

    Returns a GapAnalysis with:
    - missing_skills: appear in jobs but not in resume
    - keyword_gaps: domain terms frequent in job descriptions but absent from resume
    - strengths: resume skills that appear frequently in job postings
    - match_score: % of resume skills that match job requirements
    """
    resume_set = {s.lower() for s in resume_skills}

    # Aggregate all required skills across jobs
    all_job_skills: list[str] = []
    for skills in job_postings_skills:
        all_job_skills.extend([s.lower() for s in skills])

    from collections import Counter
    job_skill_counts = Counter(all_job_skills)

    # Skills that appear in ≥2 jobs but not in resume
    missing_skills = [
        skill for skill, count in job_skill_counts.most_common(20)
        if skill not in resume_set and count >= 2
    ]

    # Keyword gaps: high-frequency terms in descriptions not in resume
    all_desc_words: list[str] = []
    for desc in job_descriptions:
        all_desc_words.extend(_normalize(desc))

    # Filter to meaningful tech terms (len > 3, not stopwords)
    stopwords = {"with", "and", "the", "for", "you", "will", "that", "have",
                 "this", "our", "are", "your", "from", "they", "been", "work"}
    desc_word_counts = Counter(
        w for w in all_desc_words
        if len(w) > 3 and w not in stopwords and not w.isdigit()
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
    LangGraph node: computes semantic/keyword match between resume and job postings.
    """
    if state.error:
        return state

    logger.info(f"[{state.job_id}] embed_match: starting")

    resume_skills = state.resume_profile.skills if state.resume_profile else []
    job_skills_lists = [job.required_skills for job in state.job_postings]
    job_descriptions = [job.description for job in state.job_postings]

    state.gap_analysis = _keyword_gap_analysis(
        resume_skills=resume_skills,
        job_postings_skills=job_skills_lists,
        job_descriptions=job_descriptions,
    )

    logger.info(
        f"[{state.job_id}] embed_match: match_score={state.gap_analysis.match_score}, "
        f"missing={len(state.gap_analysis.missing_skills)} skills"
    )
    return state
