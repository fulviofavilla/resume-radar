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

    Strategy: target_role is the primary signal. Skills are used only to
    build a compact secondary query — too many keywords cause RemoteOK to
    return generic results.
    """
    PRIORITY_SKILLS = {
        "python", "sql", "aws", "azure", "gcp", "spark", "pyspark",
        "airflow", "docker", "kubernetes", "dbt", "kafka", "fastapi",
        "langchain", "langgraph", "pytorch", "tensorflow", "scikit-learn",
    }

    keywords = []

    if state.target_role:
        keywords.append(state.target_role)

    if state.resume_profile:
        priority = [
            s for s in state.resume_profile.skills
            if s.lower() in PRIORITY_SKILLS
        ]
        # Up to 3 priority skills — enough signal without over-filtering
        keywords.extend(priority[:3])

    return keywords


async def search_jobs_node(state: AgentState) -> AgentState:
    """
    LangGraph node: searches multiple job APIs in parallel and aggregates results.
    """
    if state.error:
        return state

    # Skip search if user provided a job description manually
    if state.job_description:
        logger.info(f"[{state.job_id}] search_jobs: skipped - manual job description provided")
        return state

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
