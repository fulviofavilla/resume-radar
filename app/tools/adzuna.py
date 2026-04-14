"""
Adzuna API client.
Free tier: 250 requests/day.
Sign up: https://developer.adzuna.com/
"""
import httpx
import re
from app.models import JobPosting
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', ' ', text).strip()


async def search_adzuna(keywords: list[str], max_results: int = 10) -> list[JobPosting]:
    """
    Search Adzuna for jobs.
    Falls back to empty list if credentials are not configured.
    """
    settings = get_settings()

    if not settings.adzuna_app_id or not settings.adzuna_api_key:
        logger.info("Adzuna credentials not set — skipping.")
        return []

    query = " ".join(keywords[:5])
    url = (
        f"https://api.adzuna.com/v1/api/jobs/{settings.adzuna_country}/search/1"
        f"?app_id={settings.adzuna_app_id}"
        f"&app_key={settings.adzuna_api_key}"
        f"&results_per_page={max_results}"
        f"&what={query}"
        f"&content-type=application/json"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.warning(f"Adzuna fetch failed: {e}")
        return []

    jobs = []
    for item in data.get("results", []):
        # Strip HTML before storing — keeps JSON output clean
        description = _strip_html(item.get("description", ""))
        jobs.append(
            JobPosting(
                title=item.get("title", "Unknown"),
                company=item.get("company", {}).get("display_name", "Unknown"),
                url=item.get("redirect_url", ""),
                description=description[:2000],
                required_skills=[],  # populated by LLM in embed_match
                source="adzuna",
            )
        )

    return jobs
