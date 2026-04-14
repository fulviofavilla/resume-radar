# 📡 ResumeRadar

> AI-powered resume analyzer. Upload your PDF, get matched against real job postings, and surface exactly what skills are holding you back.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6B35?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-1.0-E91E63?logo=databricks&logoColor=white)](https://trychroma.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22C55E.svg)](LICENSE)

---

## How it works

```
your resume.pdf
      │
      ▼
┌─────────────────┐     ┌──────────────────┐
│  parse_resume   │     │   search_jobs    │
│                 │     │                  │
│ LLM extracts:   │────▶│ RemoteOK + Adzuna│
│ • explicit      │     │ weighted keyword  │
│   skills        │     │ relevance filter  │
│ • inferred      │     └────────┬─────────┘
│   capabilities  │              │
└─────────────────┘              │
                                 ▼
                    ┌────────────────────────┐
                    │      embed_match       │
                    │                        │
                    │ OpenAI embeddings +    │
                    │ ChromaDB cosine sim    │
                    │ → match_score: 0.81    │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │    generate_report     │
                    │                        │
                    │ LLM → 5 actionable     │
                    │ recommendations        │
                    └────────────────────────┘
```

---

## Demo

```bash
# 1. Start the stack
docker compose up --build

# 2. Analyze a resume
curl -X POST http://localhost:8000/analyze \
  -F "file=@resume.pdf" \
  -F "target_role=Data Engineer"

# → {"job_id": "ae200425-...", "status": "processing"}

# 3. Get results (~20-30s)
curl http://localhost:8000/results/ae200425-... | python3 -m json.tool
```

**Output:**
```json
{
  "status": "completed",
  "resume_profile": {
    "skills": ["Python", "SQL", "AWS", "Apache Airflow", "Docker", "PySpark"],
    "inferred_skills": ["ETL pipelines", "data governance", "CI/CD", "pipeline automation"],
    "seniority": "mid",
    "years_of_experience": 2
  },
  "report": {
    "gap_analysis": {
      "match_score": 0.81,
      "strengths": ["Python", "SQL", "AWS", "Azure", "Docker", "data engineering"],
      "missing_skills": ["devops"]
    },
    "recommendations": [
      "Add DevOps skills (Jenkins, Kubernetes) — appears in 4/5 top jobs, unlocks $30-50/hr roles",
      "Highlight Apache Airflow prominently — strong differentiator for data pipeline roles",
      "Add Terraform to your stack — frequent in cloud-native data engineering postings",
      "AWS/Azure certification validates your cloud skills — high signal for remote roles",
      "Quantify pipeline impact in your resume (e.g. '90% storage reduction') — stands out in ATS"
    ],
    "jobs_analyzed": 5
  }
}
```

---

## Stack

| Layer | Tech |
|---|---|
| Agent Orchestration | LangGraph (stateful 4-node graph) |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector DB | ChromaDB 1.0 (Docker service, cosine similarity) |
| API | FastAPI + Uvicorn (async, background tasks) |
| PDF Parsing | pdfplumber |
| Job Sources | RemoteOK (no auth) + Adzuna (free tier) |
| Containerization | Docker + Docker Compose |

---

## Quickstart

**Prerequisites:** Docker Desktop · OpenAI API key

```bash
git clone https://github.com/fulviofavilla/resume-radar
cd resume-radar

cp .env.example .env
# Add your OPENAI_API_KEY to .env

docker compose up --build
```

The API starts at `http://localhost:8000`. ChromaDB runs as a separate service on port `8001` and persists embeddings across restarts via a named Docker volume.

**Optional:** Add Adzuna credentials to `.env` for broader job coverage (free tier, 250 req/day at [developer.adzuna.com](https://developer.adzuna.com/)).

---

## API Reference

### `POST /analyze`

Upload a resume PDF and start an analysis job.

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | PDF (multipart) | ✓ | Resume file, max 10 MB |
| `target_role` | string (form) | — | Focus the job search (e.g. `"Data Engineer"`) |

Returns `{ job_id, status, message }`.

### `GET /results/{job_id}`

Poll for results. Returns `status: processing` while the agent runs.

Returns the full analysis when `status: completed`:
- `resume_profile` — extracted skills, inferred capabilities, seniority
- `report.gap_analysis` — match score, strengths, missing skills
- `report.recommendations` — 5 actionable, market-aware suggestions
- `report.top_jobs` — the 5 job postings used for analysis

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "resume-radar", "version": "0.1.0"}
```

---

## Architecture

### Agent graph

```
parse_resume ──▶ search_jobs ──▶ embed_match ──▶ generate_report
     │               │               │                  │
  error?          error?          error?              END
     └───────────────┴───────────────┴──── END (early exit)
```

Each node operates on a shared `AgentState` dict. Any node can set `error` to short-circuit the graph — no exception handling scattered across the codebase.

### Semantic matching

`embed_match` uses a two-pass approach:
1. **LLM extraction** — calls `gpt-4o-mini` in parallel on each job description to extract real required skills (not noisy job board tags)
2. **Embedding + cosine similarity** — embeds both resume skills and job skills with `text-embedding-3-small`, stores in ChromaDB, queries for semantic proximity

This is what lifts `match_score` from ~0.1 (keyword overlap) to ~0.8 (semantic similarity). Skills like `"pipeline automation"` match `"data pipelines"` without exact string overlap.

**Fallback:** if ChromaDB is unreachable, `embed_match` automatically falls back to keyword gap analysis — the service stays functional.

### Job search

RemoteOK is filtered client-side using a weighted relevance score:
- Title match: 3 points
- Tag match: 2 points
- Description match: 1 point

Jobs below threshold 3 are discarded. Keywords are limited to `target_role` + top 3 priority skills from the resume to avoid over-filtering.

---

## Project Structure

```
resume-radar/
├── app/
│   ├── main.py              # FastAPI — /analyze, /results/{id}, /health
│   ├── agent.py             # LangGraph graph definition + compilation
│   ├── vector_store.py      # ChromaDB client singleton
│   ├── models.py            # Pydantic models (AgentState, ResumeProfile, Report...)
│   ├── config.py            # Settings via pydantic-settings + .env
│   ├── nodes/
│   │   ├── parse_resume.py  # PDF → text → LLM → ResumeProfile + inferred skills
│   │   ├── search_jobs.py   # Parallel job search (RemoteOK + Adzuna)
│   │   ├── embed_match.py   # OpenAI embeddings + ChromaDB gap analysis
│   │   └── generate_report.py  # LLM recommendations
│   └── tools/
│       ├── remoteok.py      # RemoteOK API client (weighted scoring, HTML strip)
│       └── adzuna.py        # Adzuna API client (HTML strip)
├── tests/
│   └── test_agent.py
├── Dockerfile
├── docker-compose.yml       # api + vectordb (ChromaDB)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Roadmap

- [x] v0.1 — MVP: PDF → job search → gap analysis → report
- [x] v0.2 — Semantic matching (ChromaDB + OpenAI embeddings), HTML sanitization
- [ ] v0.3 — Resume rewrite suggestions (improve weak bullet points)
- [ ] v0.4 — Course recommendations for identified gaps
- [ ] v1.0 — Rate limiting, Redis job store, optional frontend

---

## Contributing

PRs welcome. Open an issue first for major changes.

---

## License

MIT
