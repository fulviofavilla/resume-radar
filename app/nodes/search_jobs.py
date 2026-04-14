"""
Node 2: search_jobs
Uses the extracted resume profile to search for relevant job postings
from RemoteOK and Adzuna in parallel.
"""
import asyncio
from app.models import AgentState
from app.tools.remoteok import search_remoteok
from app.tools.adzuna import search_adzuna
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


def _build_search_keywords(state: AgentState) -> list[str]:
    """
    Build a focused keyword list for job search.
    Combines top skills from the resume + optional target role.
    """
    keywords = []

    # Target role always goes first (highest signal)
    if state.target_role:
        keywords.append(state.target_role)

    # Add top skills (cap at 8 to avoid over-filtering)
    if state.resume_profile:
        keywords.extend(state.resume_profile.skills[:8])

    return keywords


async def search_jobs_node(state: AgentState) -> AgentState:
    """
    LangGraph node: searches multiple job APIs in parallel and aggregates results.
    """
    if state.error:
        return state  # propagate error from previous node

    logger.info(f"[{state.job_id}] search_jobs: starting")
    settings = get_settings()

    keywords = _build_search_keywords(state)
    logger.info(f"[{state.job_id}] search_jobs: keywords = {keywords}")

    # Fetch from all sources in parallel
    remoteok_jobs, adzuna_jobs = await asyncio.gather(
        search_remoteok(keywords, max_results=settings.max_jobs_to_fetch),
        search_adzuna(keywords, max_results=settings.max_jobs_to_fetch),
    )

    all_jobs = remoteok_jobs + adzuna_jobs

    # Deduplicate by URL
    seen_urls = set()
    unique_jobs = []
    for job in all_jobs:
        if job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)

    # Keep top N for analysis
    state.job_postings = unique_jobs[:settings.top_jobs_for_analysis]

    if not state.job_postings:
        state.error = "No job postings found for your profile. Try providing a target_role."
        return state

    logger.info(
        f"[{state.job_id}] search_jobs: found {len(unique_jobs)} unique jobs "
        f"({len(remoteok_jobs)} RemoteOK, {len(adzuna_jobs)} Adzuna), "
        f"using top {len(state.job_postings)}"
    )
    return state
