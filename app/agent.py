"""
ResumeRadar Agent — LangGraph graph definition.

Graph:
  parse_resume → search_jobs → embed_match → generate_report
                     ↓ (on error, any node routes to END)
"""
from langgraph.graph import StateGraph, END
from app.models import AgentState
from app.nodes.parse_resume import parse_resume_node
from app.nodes.search_jobs import search_jobs_node
from app.nodes.embed_match import embed_match_node
from app.nodes.generate_report import generate_report_node
import logging

logger = logging.getLogger(__name__)


def should_continue(state: AgentState) -> str:
    """
    Conditional edge: if any node set an error, route to END immediately.
    Otherwise continue to the next node.
    """
    if state.error:
        logger.warning(f"[{state.job_id}] Agent stopping early — error: {state.error}")
        return "end"
    return "continue"


def build_agent() -> StateGraph:
    """Build and compile the ResumeRadar LangGraph agent."""

    # LangGraph requires a dict-based state; we wrap our Pydantic model
    # by converting to/from dict at the graph boundary.
    # Using dict[str, any] as the native state type for LangGraph compatibility.

    graph = StateGraph(dict)

    # --- Wrapper nodes (dict ↔ AgentState conversion) ---

    async def _parse_resume(state: dict) -> dict:
        result = await parse_resume_node(AgentState(**state))
        return result.dict()

    async def _search_jobs(state: dict) -> dict:
        result = await search_jobs_node(AgentState(**state))
        return result.dict()

    async def _embed_match(state: dict) -> dict:
        result = await embed_match_node(AgentState(**state))
        return result.dict()

    async def _generate_report(state: dict) -> dict:
        result = await generate_report_node(AgentState(**state))
        return result.dict()

    def _check_error(state: dict) -> str:
        return "end" if state.get("error") else "continue"

    # --- Register nodes ---
    graph.add_node("parse_resume", _parse_resume)
    graph.add_node("search_jobs", _search_jobs)
    graph.add_node("embed_match", _embed_match)
    graph.add_node("generate_report", _generate_report)

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
    graph.add_edge("generate_report", END)

    return graph.compile()


# Singleton — compiled once at startup
agent = build_agent()
