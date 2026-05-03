# ResumeRadar

> AI-powered resume analyzer for tech roles. Upload your PDF, get matched against real remote job postings, surface skill gaps, get targeted rewrite suggestions, and download a formatted PDF report.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1+-FF6B35?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-1.0-E91E63?logo=databricks&logoColor=white)](https://trychroma.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![CI](https://github.com/fulviofavilla/resume-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/fulviofavilla/resume-radar/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-22C55E.svg)](LICENSE)

---

![Demo](docs/resume-radar-demo.gif)

---

## How it works

```
your resume.pdf
      |
      v
┌─────────────────┐     ┌──────────────────┐
│  parse_resume   │     │   search_jobs    │
│                 │     │                  │
│ LLM extracts:   │────>│ RemoteOK + Adzuna│
│ • explicit      │     │ weighted keyword  │
│   skills        │     │ relevance filter  │
│ • inferred      │     └────────┬─────────┘
│   capabilities  │              │
└─────────────────┘              │
                                 v
                    ┌────────────────────────┐
                    │      embed_match       │
                    │                        │
                    │ OpenAI embeddings +    │
                    │ ChromaDB cosine sim    │
                    │ -> match_score: 0.81   │
                    └────────────┬───────────┘
                                 │
                                 v
                    ┌────────────────────────┐
                    │    generate_report     │
                    │                        │
                    │ LLM -> 5 actionable    │
                    │ recommendations        │
                    └────────────┬───────────┘
                                 │
                                 v
                    ┌────────────────────────┐
                    │    rewrite_resume      │
                    │                        │
                    │ LLM scores bullets,    │
                    │ rewrites weak ones     │
                    │ anchored to market     │
                    └────────────────────────┘
```

When a job description is pasted manually, `search_jobs` is skipped and the pipeline runs directly against that single posting.

> **Scope:** ResumeRadar is focused on tech roles. Job search and skill matching are tuned for this context.

---

## Quickstart

**Prerequisites:** Docker · OpenAI API key

```bash
git clone https://github.com/fulviofavilla/resume-radar
cd resume-radar

cp .env.example .env
# Add your OPENAI_API_KEY to .env

docker compose up --build
```

- **UI:** `http://localhost:8000`
- **API docs:** `http://localhost:8000/docs`

**Optional:** Add Adzuna credentials to `.env` for broader job coverage - free tier, 250 req/day at [developer.adzuna.com](https://developer.adzuna.com/).

**Using a local LLM:** Set `OPENAI_BASE_URL` and `OPENAI_MODEL` in `.env` to point at any OpenAI-compatible endpoint (Ollama, LM Studio) - no code changes needed. If you swap `OPENAI_EMBEDDING_MODEL`, run `docker compose down -v` first to clear the ChromaDB volume and avoid dimension mismatch errors.

---

## Output

```json
{
  "status": "completed",
  "resume_profile": {
    "skills": ["Python", "SQL", "AWS", "Apache Airflow", "Docker", "PySpark"],
    "inferred_skills": ["ETL pipelines", "data governance", "CI/CD"],
    "seniority": "mid",
    "years_of_experience": 2
  },
  "report": {
    "gap_analysis": {
      "match_score": 0.81,
      "strengths": ["Python", "SQL", "AWS", "Docker"],
      "missing_skills": ["dbt", "Kafka"]
    },
    "recommendations": [
      "Add dbt to your stack - appears in 4/5 top jobs, unlocks $30-50/hr roles"
    ],
    "resume_rewrites": [
      {
        "original": "Designed and optimized scalable data pipelines...",
        "rewrite": "Engineered scalable data pipelines processing 10M+ daily records...",
        "reason": "Original lacked specificity and quantification.",
        "alignment_note": "Incorporates 'data pipelines' - present in 4/5 top matching jobs.",
        "quantification_is_estimated": true
      }
    ]
  }
}
```

> When `quantification_is_estimated` is `true`, the rewrite introduced numeric metrics not present in the original. Replace them with your real numbers before updating your resume.

---

## Architecture

`embed_match` uses a two-pass approach: LLM extraction to pull real required skills from job descriptions (not noisy job board tags), then OpenAI embeddings + ChromaDB cosine similarity. This lifts `match_score` from ~0.1 (keyword overlap) to ~0.8 (semantic similarity) - skills like `"pipeline automation"` match `"data pipelines"` without exact string overlap. Falls back to keyword gap analysis if ChromaDB is unreachable.

`rewrite_resume` scores each bullet for market impact (1-10) and rewrites those scoring 6 or below, anchored to `missing_skills` or the union of required skills across top jobs for strong profiles.

---

## Project Structure

```
resume-radar/
├── app/
│   ├── main.py              # FastAPI endpoints
│   ├── agent.py             # LangGraph graph + SSE progress queue
│   ├── pdf_report.py        # weasyprint PDF generation
│   ├── vector_store.py      # ChromaDB client singleton
│   ├── models.py            # Pydantic models
│   ├── config.py            # pydantic-settings + .env
│   ├── nodes/
│   │   ├── parse_resume.py
│   │   ├── search_jobs.py
│   │   ├── embed_match.py
│   │   ├── generate_report.py
│   │   └── rewrite_resume.py
│   └── tools/
│       ├── remoteok.py
│       └── adzuna.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── hooks/useAnalysis.js
│       └── components/
├── tests/
│   └── test_agent.py
├── .github/
│   ├── dependabot.yml
│   └── workflows/ci.yml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Roadmap

- [x] v0.1 - MVP: PDF -> job search -> gap analysis -> report
- [x] v0.2 - Semantic matching (ChromaDB + OpenAI embeddings)
- [x] v0.3 - Resume rewrite suggestions: bullet scoring, market-anchored rewrites
- [x] v0.4 - SSE progress streaming, static frontend, PDF report download
- [x] v0.5 - Redis job store, rate limiting
- [x] v0.6 - PDF report redesign, self-hosted fonts
- [x] v0.7 - Vite + React frontend, manual job description input
- [x] v1.0 - Open source release: internal docker network, 1h TTL, Ollama support

---

## Contributing

PRs welcome. Open an issue first for major changes.

---

## License

MIT