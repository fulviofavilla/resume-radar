"""
RemoteOK API client.
Public API — no auth required.
Docs: https://remoteok.com/api

Filtering strategy:
  RemoteOK returns all jobs — we filter client-side using a weighted score:
  - Title match:       3 points per keyword  (strongest signal)
  - Tag match:         2 points per keyword
  - Description match: 1 point per keyword
  Jobs scoring below threshold (3) are discarded.
"""
import httpx
import re
from app.models import JobPosting
import logging

logger = logging.getLogger(__name__)

REMOTEOK_URL = "https://remoteok.com/api"
SCORE_THRESHOLD = 3


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', ' ', text).strip()


async def search_remoteok(keywords: list[str], max_results: int = 10) -> list[JobPosting]:
    """
    Search RemoteOK for jobs matching the given keywords.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                REMOTEOK_URL,
                headers={"User-Agent": "ResumeRadar/1.0 (portfolio project)"},
            )
            response.raise_for_status()

        raw = response.json()
        jobs_raw = [j for j in raw if isinstance(j, dict) and "position" in j]

    except Exception as e:
        logger.warning(f"RemoteOK fetch failed: {e}")
        return []

    keywords_lower = [k.lower() for k in keywords]
    matched: list[tuple[int, JobPosting]] = []

    for job in jobs_raw:
        title = job.get("position", "").lower()
        original_description = job.get("description", "")
        description_lower = original_description.lower()
        original_tags = job.get("tags", [])
        tag_text = " ".join(t.lower() for t in original_tags)

        # Weighted relevance score
        score = (
            sum(3 for kw in keywords_lower if kw in title) +
            sum(2 for kw in keywords_lower if kw in tag_text) +
            sum(1 for kw in keywords_lower if kw in description_lower)
        )

        if score < SCORE_THRESHOLD:
            continue

        # Strip HTML before storing — keeps JSON output clean
        clean_description = _strip_html(original_description)

        matched.append((
            score,
            JobPosting(
                title=job.get("position", "Unknown"),
                company=job.get("company", "Unknown"),
                url=job.get("url", f"https://remoteok.com/remote-jobs/{job.get('id', '')}"),
                description=clean_description[:2000],  # clean, capped
                required_skills=original_tags,          # replaced by LLM in embed_match
                source="remoteok",
            )
        ))

    matched.sort(key=lambda x: x[0], reverse=True)
    results = [job for _, job in matched[:max_results]]

    logger.info(f"RemoteOK: {len(jobs_raw)} total jobs → {len(results)} matched (threshold={SCORE_THRESHOLD})")
    return results
