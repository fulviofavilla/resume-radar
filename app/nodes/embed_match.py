"""
Node 3: embed_match
Semantic matching between the resume and job postings using ChromaDB + OpenAI embeddings.

Architecture:
  1. LLM extracts clean required_skills from each job description (parallel)
  2. Job skills are embedded with text-embedding-3-small and stored in ChromaDB
  3. Resume skills are embedded and queried against the collection
  4. Cosine similarity scores drive match_score, strengths, and missing_skills

Fallback:
  If ChromaDB is unavailable, falls back to keyword gap analysis automatically.
  This makes the node resilient during local dev without the vectordb service.
"""
import asyncio
import re
from collections import Counter
from openai import AsyncOpenAI
from app.models import AgentState, GapAnalysis
from app.nodes.parse_resume import extract_skills_from_job_description
from app.vector_store import get_collection
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

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
    return re.sub(r'<[^>]+>', ' ', text)


def _normalize(text: str) -> set[str]:
    return {w.strip(".,()") for w in text.lower().split()}


# ── Embedding helpers ─────────────────────────────────────────────────────────

async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using OpenAI text-embedding-3-small.
    Returns a list of embedding vectors in the same order as input.
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


# ── Semantic matching (ChromaDB) ──────────────────────────────────────────────

async def _semantic_gap_analysis(
    job_id: str,
    resume_skills: list[str],
    job_postings_skills: list[list[str]],
) -> GapAnalysis:
    """
    Compute gap analysis using ChromaDB cosine similarity.

    Workflow:
      1. Flatten all job skills into documents, store in ChromaDB
      2. Embed resume skills and query against the collection
      3. Cosine similarity scores drive match_score, strengths, missing_skills

    ChromaDB HTTP client is synchronous — wrapped in asyncio.to_thread
    to avoid blocking the FastAPI event loop.
    """
    import asyncio as _asyncio

    collection = await _asyncio.to_thread(get_collection, f"jobs_{job_id}")

    # Flatten unique job skills
    all_job_skills: list[str] = []
    for skills in job_postings_skills:
        all_job_skills.extend(skills)
    unique_job_skills = list({s.lower() for s in all_job_skills if s.lower() not in SKILL_NOISE})

    if not unique_job_skills:
        raise ValueError("No job skills to embed")

    # Embed job skills and store
    job_embeddings = await _embed_texts(unique_job_skills)
    await _asyncio.to_thread(
        collection.add,
        ids=[f"skill_{i}" for i in range(len(unique_job_skills))],
        embeddings=job_embeddings,
        documents=unique_job_skills,
    )
    logger.info(f"[{job_id}] embed_match: stored {len(unique_job_skills)} job skill embeddings")

    # Embed resume skills and query
    all_resume_skills = [s.lower() for s in resume_skills if s.lower() not in SKILL_NOISE]
    if not all_resume_skills:
        raise ValueError("No resume skills to embed")

    resume_embeddings = await _embed_texts(all_resume_skills)

    similarities: list[float] = []
    matched_job_skills: list[str] = []

    for skill, embedding in zip(all_resume_skills, resume_embeddings):
        results = await _asyncio.to_thread(
            collection.query,
            query_embeddings=[embedding],
            n_results=min(3, len(unique_job_skills)),
            include=["documents", "distances"],
        )
        top_distances = results["distances"][0]
        # Cosine distance → similarity (0=identical → 1.0, 2=opposite → 0.0)
        top_similarities = [1 - (d / 2) for d in top_distances]
        best_similarity = max(top_similarities) if top_similarities else 0.0
        similarities.append(best_similarity)

        if best_similarity >= 0.75:
            matched_job_skills.append(skill)

    # Skills frequent in jobs but absent from resume
    job_skill_counts = Counter(s.lower() for skills in job_postings_skills for s in skills)
    missing_skills = [
        skill for skill, count in job_skill_counts.most_common(20)
        if skill not in {s.lower() for s in resume_skills}
        and skill not in SKILL_NOISE
        and count >= 2
    ]

    match_score = sum(similarities) / len(similarities) if similarities else 0.0

    return GapAnalysis(
        missing_skills=missing_skills[:10],
        keyword_gaps=[],  # semantic matching replaces keyword_gaps
        strengths=matched_job_skills,
        match_score=round(match_score, 2),
    )


# ── Keyword fallback ──────────────────────────────────────────────────────────

def _keyword_gap_analysis(
    resume_skills: list[str],
    job_postings_skills: list[list[str]],
    job_descriptions: list[str],
) -> GapAnalysis:
    """
    Keyword-based fallback when ChromaDB is unavailable.
    Identical to v0.1 logic — kept as safety net.
    """
    resume_set = {s.lower() for s in resume_skills}
    all_job_skills: list[str] = []
    for skills in job_postings_skills:
        all_job_skills.extend([s.lower() for s in skills])

    job_skill_counts = Counter(all_job_skills)

    missing_skills = [
        skill for skill, count in job_skill_counts.most_common(20)
        if skill not in resume_set and skill not in SKILL_NOISE and count >= 2
    ]

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

    strengths = [s for s in resume_skills if s.lower() in job_skill_counts]
    top_job_skills = {skill for skill, _ in job_skill_counts.most_common(20)}
    matched = resume_set.intersection(top_job_skills)
    match_score = len(matched) / len(top_job_skills) if top_job_skills else 0.0

    return GapAnalysis(
        missing_skills=missing_skills[:10],
        keyword_gaps=keyword_gaps,
        strengths=strengths,
        match_score=round(match_score, 2),
    )


# ── Node ──────────────────────────────────────────────────────────────────────

async def embed_match_node(state: AgentState) -> AgentState:
    """
    LangGraph node: extracts real skills from job descriptions via LLM,
    then computes semantic gap analysis using ChromaDB embeddings.
    Falls back to keyword matching if ChromaDB is unavailable.
    """
    if state.error:
        return state

    # Manual job description - synthesize a JobPosting so the rest of the pipeline runs unchanged
    if state.job_description and not state.job_postings:
        from app.models import JobPosting
        state.job_postings = [
            JobPosting(
                title="Manual Job Description",
                company="—",
                url="",
                description=state.job_description,
                required_skills=[],
                source="manual",
            )
        ]
        logger.info(f"[{state.job_id}] embed_match: using manual job description as single posting")

    logger.info(f"[{state.job_id}] embed_match: extracting skills from {len(state.job_postings)} jobs")

    # Step 1: Extract real skills from job descriptions in parallel
    extracted_skills_lists = await asyncio.gather(
        *[extract_skills_from_job_description(_strip_html(job.description))
          for job in state.job_postings]
    )

    for job, skills in zip(state.job_postings, extracted_skills_lists):
        if skills:
            job.required_skills = skills
            logger.info(f"[{state.job_id}] embed_match: '{job.title[:40]}' → {skills}")

    # Step 2: Combine explicit + inferred resume skills
    explicit = state.resume_profile.skills if state.resume_profile else []
    inferred = state.resume_profile.inferred_skills if state.resume_profile else []
    all_resume_skills = explicit + inferred

    job_skills_lists = [job.required_skills for job in state.job_postings]
    job_descriptions = [job.description for job in state.job_postings]

    # Step 3: Semantic matching via ChromaDB, fallback to keyword
    try:
        state.gap_analysis = await _semantic_gap_analysis(
            job_id=state.job_id,
            resume_skills=all_resume_skills,
            job_postings_skills=job_skills_lists,
        )
        logger.info(f"[{state.job_id}] embed_match: semantic matching complete")
    except Exception as e:
        logger.warning(f"[{state.job_id}] embed_match: ChromaDB unavailable ({e}), falling back to keyword matching")
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
