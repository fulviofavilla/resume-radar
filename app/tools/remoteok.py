"""
RemoteOK API client.
Public API — no auth required.
Docs: https://remoteok.com/api
"""
import httpx
from app.models import JobPosting
import logging

logger = logging.getLogger(__name__)

REMOTEOK_URL = "https://remoteok.com/api"


async def search_remoteok(keywords: list[str], max_results: int = 10) -> list[JobPosting]:
    """
    Search RemoteOK for jobs matching the given keywords.
    RemoteOK returns all jobs; we filter client-side by keyword relevance.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                REMOTEOK_URL,
                headers={"User-Agent": "ResumeRadar/1.0 (portfolio project)"},
            )
            response.raise_for_status()

        raw = response.json()
        # First element is metadata — skip it
        jobs_raw = [j for j in raw if isinstance(j, dict) and "position" in j]

    except Exception as e:
        logger.warning(f"RemoteOK fetch failed: {e}")
        return []

    # Filter by keyword relevance
    keywords_lower = [k.lower() for k in keywords]
    matched: list[JobPosting] = []

    for job in jobs_raw:
        text = f"{job.get('position', '')} {job.get('description', '')} {' '.join(job.get('tags', []))}".lower()
        score = sum(1 for kw in keywords_lower if kw in text)
        if score == 0:
            continue

        tags = job.get("tags", [])
        matched.append(
            JobPosting(
                title=job.get("position", "Unknown"),
                company=job.get("company", "Unknown"),
                url=job.get("url", f"https://remoteok.com/remote-jobs/{job.get('id', '')}"),
                description=job.get("description", "")[:2000],  # cap to avoid token bloat
                required_skills=tags,
                source="remoteok",
            )
        )

    # Sort by keyword overlap (most relevant first)
    matched.sort(
        key=lambda j: sum(1 for kw in keywords_lower if kw in j.description.lower() + j.title.lower()),
        reverse=True,
    )
    return matched[:max_results]
