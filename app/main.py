"""
ResumeRadar — FastAPI application.

Endpoints:
  POST /analyze              — upload PDF, start analysis job (async)
  GET  /results/{job_id}     — poll for results
  GET  /progress/{job_id}    — SSE stream of node-level progress events
  GET  /health               — health check
"""
import asyncio
import json
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.models import (
    AnalyzeResponse,
    ResultsResponse,
    JobStatus,
    AgentState,
)
from app.agent import agent, register_progress_queue, unregister_progress_queue

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
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

async def _run_analysis(job_id: str, pdf_bytes: bytes, target_role: str | None) -> None:
    """Runs the LangGraph agent and writes results to job store.
    Registers a progress queue before invoking so SSE can stream node events.
    """
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
        _job_store[job_id] = final_state
        status = "failed" if final_state.get("error") else "completed"
        logger.info(f"[{job_id}] Analysis {status}")

        # Signal SSE stream that the pipeline is done
        await queue.put({"step": "done", "message": "Analysis complete.", "status": status})
    except Exception as e:
        logger.error(f"[{job_id}] Unhandled agent error: {e}", exc_info=True)
        _job_store[job_id] = {"job_id": job_id, "error": str(e)}
        await queue.put({"step": "error", "message": str(e), "status": "failed"})
    finally:
        unregister_progress_queue(job_id)


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
    Returns a job_id to poll /results/{job_id} or stream /progress/{job_id}.
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
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    # If the job already completed before the client connected, return immediately
    job = _job_store[job_id]
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
            # Job finished before we could attach — return terminal event
            job = _job_store.get(job_id, {})
            status = "failed" if job.get("error") else "completed"
            yield f"data: {json.dumps({'step': 'done', 'message': 'Analysis complete.', 'status': status})}\n\n"
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                # Keep-alive ping to prevent proxy/client timeouts
                yield ": keep-alive\n\n"
                continue

            yield f"data: {json.dumps(event)}\n\n"

            # Close stream on terminal events
            if event.get("step") in ("done", "error"):
                break

    return StreamingResponse(_stream_events(), media_type="text/event-stream")


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
    return {"status": "ok", "service": "resume-radar", "version": "0.4.0"}