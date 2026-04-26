"""
ResumeRadar — FastAPI application.

Endpoints:
  POST /analyze              — upload PDF, start analysis job (async)
  GET  /results/{job_id}     — poll for results
  GET  /progress/{job_id}    — SSE stream of node-level progress events
  GET  /results/{job_id}/pdf — download PDF report
  GET  /health               — health check
"""
import asyncio
import json
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.models import (
    AnalyzeResponse,
    ResultsResponse,
    JobStatus,
    AgentState,
)
from app.agent import agent, register_progress_queue, unregister_progress_queue
from app.config import get_settings
from app.pdf_report import generate_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

_redis: aioredis.Redis | None = None
_JOB_TTL = 60 * 60 * 24  # 24 hours


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def _job_set(job_id: str, data: dict[str, Any]) -> None:
    r = await _get_redis()
    await r.set(f"job:{job_id}", json.dumps(data, default=str), ex=_JOB_TTL)


async def _job_get(job_id: str) -> dict[str, Any] | None:
    r = await _get_redis()
    raw = await r.get(f"job:{job_id}")
    return json.loads(raw) if raw else None


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ResumeRadar starting up 📡")
    # Eagerly connect and verify Redis is reachable
    r = await _get_redis()
    await r.ping()
    logger.info("Redis connection verified ✅")
    yield
    if _redis:
        await _redis.aclose()
    logger.info("ResumeRadar shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ResumeRadar",
    description="AI-powered resume analyzer — match your profile against real jobs, surface skill gaps.",
    version="0.6.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/static/index.html")


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

async def _run_analysis(job_id: str, pdf_bytes: bytes, target_role: str | None) -> None:
    """Runs the LangGraph agent and writes results to Redis."""
    logger.info(f"[{job_id}] Analysis started")

    queue: asyncio.Queue = asyncio.Queue()
    register_progress_queue(job_id, queue)

    initial_state = AgentState(
        job_id=job_id,
        target_role=target_role,
        resume_bytes=pdf_bytes,
    ).dict()

    try:
        final_state = await agent.ainvoke(initial_state)
        await _job_set(job_id, final_state)
        status = "failed" if final_state.get("error") else "completed"
        logger.info(f"[{job_id}] Analysis {status}")
        await queue.put({"step": "done", "message": "Analysis complete.", "status": status})
    except Exception as e:
        logger.error(f"[{job_id}] Unhandled agent error: {e}", exc_info=True)
        await _job_set(job_id, {"job_id": job_id, "error": str(e)})
        await queue.put({"step": "error", "message": str(e), "status": "failed"})
    finally:
        unregister_progress_queue(job_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=AnalyzeResponse, status_code=202)
@limiter.limit("5/hour")
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Resume PDF"),
    target_role: str | None = Form(default=None, description="Optional target role (e.g. 'Data Engineer')"),
):
    """
    Upload a resume PDF and start an analysis job.
    Returns a job_id to poll /results/{job_id} or stream /progress/{job_id}.
    Rate limited to 5 requests per hour per IP.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 10 MB.")

    job_id = str(uuid.uuid4())
    await _job_set(job_id, {"job_id": job_id, "status": JobStatus.PROCESSING})

    background_tasks.add_task(_run_analysis, job_id, pdf_bytes, target_role)

    return AnalyzeResponse(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        message=f"Analysis started. Stream progress at /progress/{job_id} or poll /results/{job_id}.",
    )


@app.get("/progress/{job_id}")
async def progress(job_id: str):
    """
    SSE endpoint — streams node-level progress events as the agent runs.

    Each event is a JSON object:
      {"step": "<node_name>", "message": "<human readable>"}

    Terminal events:
      {"step": "done",  "message": "Analysis complete.", "status": "completed"}
      {"step": "error", "message": "<error>",            "status": "failed"}

    The stream closes automatically after a terminal event.

    Example (curl):
      curl -N http://localhost:8000/progress/<job_id>
    """
    job = await _job_get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    # If the job already completed before the client connected, return immediately
    if job.get("report") or job.get("error"):
        status = "failed" if job.get("error") else "completed"
        msg = job.get("error") or "Analysis already completed."

        async def _already_done() -> AsyncGenerator[str, None]:
            yield f"data: {json.dumps({'step': 'done', 'message': msg, 'status': status})}\n\n"

        return StreamingResponse(_already_done(), media_type="text/event-stream")

    async def _stream_events() -> AsyncGenerator[str, None]:
        # Poll until the background task registers the queue (tiny race window)
        for _ in range(20):
            from app.agent import _progress_queues
            if job_id in _progress_queues:
                break
            await asyncio.sleep(0.1)

        from app.agent import _progress_queues
        queue = _progress_queues.get(job_id)

        if not queue:
            job = await _job_get(job_id) or {}
            status = "failed" if job.get("error") else "completed"
            yield f"data: {json.dumps({'step': 'done', 'message': 'Analysis complete.', 'status': status})}\n\n"
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue

            yield f"data: {json.dumps(event)}\n\n"

            if event.get("step") in ("done", "error"):
                break

    return StreamingResponse(_stream_events(), media_type="text/event-stream")


@app.get("/results/{job_id}", response_model=ResultsResponse)
async def get_results(job_id: str):
    """
    Poll for analysis results.
    Returns status=processing while the agent is running.
    """
    job = await _job_get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    if job.get("status") == JobStatus.PROCESSING and not job.get("report") and not job.get("error"):
        return ResultsResponse(job_id=job_id, status=JobStatus.PROCESSING)

    if job.get("error"):
        return ResultsResponse(
            job_id=job_id,
            status=JobStatus.FAILED,
            error=job["error"],
        )

    return ResultsResponse(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        resume_profile=job.get("resume_profile"),
        report=job.get("report"),
    )


@app.get("/results/{job_id}/pdf")
async def get_results_pdf(job_id: str):
    """
    Generate and download a PDF report for a completed analysis job.
    """
    job = await _job_get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job.get("error"):
        raise HTTPException(status_code=400, detail="Cannot generate PDF: analysis failed.")
    if not job.get("report"):
        raise HTTPException(status_code=400, detail="Analysis not yet completed.")

    results = ResultsResponse(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        resume_profile=job.get("resume_profile"),
        report=job.get("report"),
    )

    try:
        pdf_bytes = generate_pdf(results)
    except Exception as e:
        logger.error(f"[{job_id}] PDF generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=resume-radar-{job_id[:8]}.pdf"},
    )


@app.get("/health")
async def health():
    r = await _get_redis()
    redis_ok = await r.ping()
    return {
        "status": "ok",
        "service": "resume-radar",
        "version": "0.6.0",
        "redis": "ok" if redis_ok else "unreachable",
    }