"""
Node 5: rewrite_resume
Analyzes the candidate's raw resume text and suggests targeted rewrites for
weak bullet points and the professional summary, grounded in the gap analysis
and top matching job postings.

Strategy:
  1. LLM segments the raw text into labeled sections (Experience, Summary, etc.)
  2. Second LLM call scores each bullet for impact and market relevance,
     rewrites weak ones, and returns an alignment_note per suggestion
     indicating which market skills each rewrite incorporates

Market context anchor:
  Uses missing_skills when available. Falls back to the union of required_skills
  across top job postings when missing_skills is empty (strong-profile case),
  so rewrites always have a real market signal to work with.

This is intentionally a separate node (not bolted onto generate_report) to
keep responsibilities clean and to allow the rewrite step to be skipped or
mocked independently in tests.
"""
import json
from openai import AsyncOpenAI
from app.models import AgentState, RewriteSuggestion
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

SEGMENT_PROMPT = """
You are a resume parser. Extract the key text segments from this resume that are
worth improving: the professional summary (if present) and experience bullet points.

Return ONLY valid JSON — no markdown, no explanation:
{{
  "summary": "<the summary/objective paragraph, or empty string if absent>",
  "bullets": [
    {{"text": "<bullet point text>", "section": "<job title or 'Summary'>"}},
    ...
  ]
}}

Rules:
- Include up to 12 bullets total (prioritize recent roles)
- Preserve the original wording exactly — do not paraphrase
- section = the job title or company context this bullet belongs to
- If no summary exists, return empty string for summary

Resume:
---
{raw_text}
---
"""

REWRITE_PROMPT = """
You are a senior technical recruiter helping a candidate rewrite weak resume bullets
to better match the current job market.

Candidate context:
- Explicit skills: {skills}
- Inferred capabilities: {inferred_skills}
- Seniority: {seniority}
- Strengths already valued by the market: {strengths}

Target market context — skills most valued in matching jobs: {market_skills}
(Note: these are {market_skills_source})

Top matching job titles: {job_titles}

Bullets to evaluate and rewrite (JSON array):
{bullets_json}

Instructions:
- Score each bullet from 1-10 for market impact (specificity, quantification, relevance to target roles)
- Rewrite only bullets scoring 6 or below — skip strong bullets
- If a summary exists, always include it for rewriting
- Each rewrite must: use strong action verbs, add quantification where plausible,
  and naturally incorporate 1-2 skills from the target market context IF they are
  genuinely supported by the candidate's actual experience
  (never hallucinate skills the candidate does not have)
- reason: 1 sentence explaining what was weak and what the rewrite fixes
- alignment_note: 1 sentence naming which market skills the rewrite incorporates
  and how frequently they appear in the top jobs (e.g. "Incorporates 'dbt' and
  'data mesh' — present in 3/5 top matching jobs").
  If no market skills were incorporated, set to empty string.
- quantification_is_estimated: true if the rewrite introduces any numeric metric
  (%, x faster, N records, etc.) that was NOT present in the original bullet.
  false if the rewrite only rephrases or uses numbers already in the original.

Return ONLY valid JSON — no markdown, no explanation:
{{
  "rewrites": [
    {{
      "original": "<exact original text>",
      "rewrite": "<improved version>",
      "reason": "<one sentence explanation>",
      "section": "<section label from input>",
      "alignment_note": "<market alignment note or empty string>",
      "quantification_is_estimated": true | false
    }},
    ...
  ]
}}

Return an empty array if all bullets are already strong (score > 6).
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_market_skills(
    missing_skills: list[str],
    job_postings: list,
) -> tuple[str, str]:
    """
    Returns (market_skills_str, source_description) for the REWRITE_PROMPT.

    Prefers missing_skills (direct gap signal). Falls back to the union of
    required_skills from top job postings when missing_skills is empty —
    this happens when the candidate's profile already matches well (high
    match_score) but rewrites can still be anchored to what the market values.
    """
    if missing_skills:
        return (
            ", ".join(missing_skills),
            "skills that appear in target jobs but are absent from your resume",
        )

    # Fallback: union of all required_skills across job postings, deduplicated
    seen: set[str] = set()
    market_skills: list[str] = []
    for job in job_postings:
        for skill in job.required_skills:
            key = skill.lower()
            if key not in seen:
                seen.add(key)
                market_skills.append(skill)

    if market_skills:
        return (
            ", ".join(market_skills[:20]),  # cap to avoid prompt bloat
            "skills most frequently required across top matching jobs (your profile already covers the key gaps)",
        )

    return ("", "no specific skill gaps identified")


# ── Node ──────────────────────────────────────────────────────────────────────

async def rewrite_resume_node(state: AgentState) -> AgentState:
    """
    LangGraph node: generates resume rewrite suggestions based on gap analysis.
    Non-blocking — if this node fails, it logs a warning and leaves
    report.resume_rewrites as an empty list rather than failing the whole job.
    """
    if state.error or not state.report or not state.resume_profile:
        return state

    logger.info(f"[{state.job_id}] rewrite_resume: starting")
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    profile = state.resume_profile
    gaps = state.gap_analysis
    jobs = state.job_postings

    # ── Step 1: segment raw resume into bullets + summary ─────────────────────
    try:
        seg_response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": SEGMENT_PROMPT.format(
                        raw_text=profile.raw_text[:8000]
                    ),
                }
            ],
            temperature=0,
        )
        raw = seg_response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        segments = json.loads(raw)
    except Exception as e:
        logger.warning(f"[{state.job_id}] rewrite_resume: segmentation failed — {e}")
        return state

    bullets = segments.get("bullets", [])
    summary = segments.get("summary", "")

    all_items = []
    if summary:
        all_items.append({"text": summary, "section": "Summary"})
    all_items.extend(bullets)

    if not all_items:
        logger.info(f"[{state.job_id}] rewrite_resume: no segments found, skipping")
        return state

    # ── Resolve market skills anchor ──────────────────────────────────────────
    missing = gaps.missing_skills if gaps else []
    market_skills_str, market_skills_source = _resolve_market_skills(missing, jobs)

    logger.info(
        f"[{state.job_id}] rewrite_resume: market anchor — "
        f"{'missing_skills' if missing else 'job required_skills fallback'} "
        f"({len(market_skills_str.split(',')) if market_skills_str else 0} skills)"
    )

    # ── Step 2: rewrite weak bullets ─────────────────────────────────────────
    try:
        rw_response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": REWRITE_PROMPT.format(
                        skills=", ".join(profile.skills),
                        inferred_skills=", ".join(profile.inferred_skills),
                        seniority=profile.seniority,
                        strengths=", ".join(gaps.strengths) if gaps else "",
                        market_skills=market_skills_str,
                        market_skills_source=market_skills_source,
                        job_titles=", ".join(j.title for j in jobs),
                        bullets_json=json.dumps(all_items, ensure_ascii=False),
                    ),
                }
            ],
            temperature=0.4,
        )
        raw = rw_response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        rewrites_raw = data.get("rewrites", [])
    except Exception as e:
        logger.warning(f"[{state.job_id}] rewrite_resume: rewrite LLM call failed — {e}")
        return state

    suggestions = []
    for item in rewrites_raw:
        try:
            suggestions.append(
                RewriteSuggestion(
                    original=item["original"],
                    rewrite=item["rewrite"],
                    reason=item["reason"],
                    section=item.get("section", "Experience"),
                    alignment_note=item.get("alignment_note", ""),
                    quantification_is_estimated=bool(item.get("quantification_is_estimated", False)),
                )
            )
        except Exception:
            continue

    state.report.resume_rewrites = suggestions

    logger.info(
        f"[{state.job_id}] rewrite_resume: done — "
        f"{len(suggestions)} suggestions generated"
    )
    return state
