"""
ResumeRadar — FastAPI application.

Endpoints:
  POST /analyze          — upload PDF, start analysis job (async)
  GET  /results/{job_id} — poll for results
  GET  /health           — health check
"""
import asyncio
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    AnalyzeResponse,
    ResultsResponse,
    JobStatus,
    AgentState,
)
from app.agent import agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# In-memory job store (swap for Redis in production)
_job_store: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ResumeRadar starting up 📡")
    yield
    logger.info("ResumeRadar shutting down")


app = FastAPI(
    title="ResumeRadar",
    description="AI-powered resume analyzer — match your profile against real jobs, surface skill gaps.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

async def _run_analysis(job_id: str, pdf_bytes: bytes, target_role: str | None) -> None:
    """Runs the LangGraph agent asynchronously and writes results to job store."""
    logger.info(f"[{job_id}] Analysis started")

    initial_state = AgentState(
        job_id=job_id,
        target_role=target_role,
        resume_bytes=pdf_bytes,
    ).dict()

    try:
        final_state = await agent.ainvoke(initial_state)
        _job_store[job_id] = final_state
        status = "failed" if final_state.get("error") else "completed"
        logger.info(f"[{job_id}] Analysis {status}")
    except Exception as e:
        logger.error(f"[{job_id}] Unhandled agent error: {e}", exc_info=True)
        _job_store[job_id] = {"job_id": job_id, "error": str(e)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=AnalyzeResponse, status_code=202)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Resume PDF"),
    target_role: str | None = Form(default=None, description="Optional target role (e.g. 'Data Engineer')"),
):
    """
    Upload a resume PDF and start an analysis job.
    Returns a job_id to poll for results.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 10 MB.")

    job_id = str(uuid.uuid4())
    _job_store[job_id] = {"job_id": job_id, "status": JobStatus.PROCESSING}

    background_tasks.add_task(_run_analysis, job_id, pdf_bytes, target_role)

    return AnalyzeResponse(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        message=f"Analysis started. Poll /results/{job_id} for updates.",
    )


@app.get("/results/{job_id}", response_model=ResultsResponse)
async def get_results(job_id: str):
    """
    Poll for analysis results.
    Returns status=processing while the agent is running.
    """
    job = _job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    # Still processing
    if job.get("status") == JobStatus.PROCESSING and not job.get("report") and not job.get("error"):
        return ResultsResponse(job_id=job_id, status=JobStatus.PROCESSING)

    # Failed
    if job.get("error"):
        return ResultsResponse(
            job_id=job_id,
            status=JobStatus.FAILED,
            error=job["error"],
        )

    # Completed
    return ResultsResponse(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        resume_profile=job.get("resume_profile"),
        report=job.get("report"),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "resume-radar", "version": "0.1.0"}
