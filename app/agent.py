"""
ResumeRadar Agent — LangGraph graph definition.

Graph:
  parse_resume → search_jobs → embed_match → generate_report → rewrite_resume
                     ↓ (on error, any node routes to END)

Progress events:
  Each node publishes a ProgressEvent to an asyncio.Queue before executing.
  The SSE endpoint in main.py consumes this queue and streams events to the client.
  Use register_progress_queue(job_id, queue) before invoking the agent,
  and unregister_progress_queue(job_id) after completion.
"""
import asyncio
from langgraph.graph import StateGraph, END
from app.models import AgentState
from app.nodes.parse_resume import parse_resume_node
from app.nodes.search_jobs import search_jobs_node
from app.nodes.embed_match import embed_match_node
from app.nodes.generate_report import generate_report_node
from app.nodes.rewrite_resume import rewrite_resume_node
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Progress event system
# ---------------------------------------------------------------------------

# Map of job_id → asyncio.Queue for SSE progress streaming
_progress_queues: dict[str, asyncio.Queue] = {}


def register_progress_queue(job_id: str, queue: asyncio.Queue) -> None:
    _progress_queues[job_id] = queue


def unregister_progress_queue(job_id: str) -> None:
    _progress_queues.pop(job_id, None)


async def _emit(job_id: str, step: str, message: str) -> None:
    """Publish a progress event to the job's queue, if one is registered."""
    queue = _progress_queues.get(job_id)
    if queue:
        await queue.put({"step": step, "message": message})


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_agent() -> StateGraph:
    """Build and compile the ResumeRadar LangGraph agent."""

    graph = StateGraph(dict)

    # --- Wrapper nodes (dict ↔ AgentState conversion + progress emission) ---

    async def _parse_resume(state: dict) -> dict:
        await _emit(state["job_id"], "parse_resume", "Parsing resume and extracting skills...")
        result = await parse_resume_node(AgentState(**state))
        return result.dict()

    async def _search_jobs(state: dict) -> dict:
        await _emit(state["job_id"], "search_jobs", "Searching job postings...")
        result = await search_jobs_node(AgentState(**state))
        return result.dict()

    async def _embed_match(state: dict) -> dict:
        await _emit(state["job_id"], "embed_match", "Computing semantic match score...")
        result = await embed_match_node(AgentState(**state))
        return result.dict()

    async def _generate_report(state: dict) -> dict:
        await _emit(state["job_id"], "generate_report", "Generating recommendations...")
        result = await generate_report_node(AgentState(**state))
        return result.dict()

    async def _rewrite_resume(state: dict) -> dict:
        await _emit(state["job_id"], "rewrite_resume", "Generating resume rewrite suggestions...")
        result = await rewrite_resume_node(AgentState(**state))
        return result.dict()

    def _check_error(state: dict) -> str:
        return "end" if state.get("error") else "continue"

    # --- Register nodes ---
    graph.add_node("parse_resume", _parse_resume)
    graph.add_node("search_jobs", _search_jobs)
    graph.add_node("embed_match", _embed_match)
    graph.add_node("generate_report", _generate_report)
    graph.add_node("rewrite_resume", _rewrite_resume)

    # --- Define edges ---
    graph.set_entry_point("parse_resume")

    graph.add_conditional_edges(
        "parse_resume",
        _check_error,
        {"continue": "search_jobs", "end": END},
    )
    graph.add_conditional_edges(
        "search_jobs",
        _check_error,
        {"continue": "embed_match", "end": END},
    )
    graph.add_conditional_edges(
        "embed_match",
        _check_error,
        {"continue": "generate_report", "end": END},
    )
    graph.add_edge("generate_report", "rewrite_resume")
    graph.add_edge("rewrite_resume", END)

    return graph.compile()


# Singleton — compiled once at startup
agent = build_agent()