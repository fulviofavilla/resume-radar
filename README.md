# 📡 ResumeRadar

> AI-powered resume analyzer that matches your profile against real job postings and surfaces skill gaps — so you know exactly what to learn next.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1+-orange?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What it does

1. **Upload your resume** (PDF) via the API
2. **LLM extracts** your skills, experience, and seniority level
3. **Searches real job postings** (RemoteOK + Adzuna) matching your profile
4. **Semantic gap analysis** — compares your profile against what top jobs demand
5. **Generates a report** with missing skills, keyword gaps, and actionable recommendations

---

## Stack

| Layer | Tech |
|---|---|
| Orchestration | LangGraph (stateful agent graph) |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | `text-embedding-3-small` |
| Vector DB | ChromaDB (local) |
| API | FastAPI + Uvicorn |
| PDF Parsing | pdfplumber |
| Job Sources | RemoteOK API, Adzuna API |
| Containerization | Docker + Docker Compose |

---

## Quickstart

### Prerequisites
- Docker & Docker Compose
- OpenAI API key
- Adzuna API credentials (free tier — [sign up here](https://developer.adzuna.com/))

### Run with Docker

```bash
git clone https://github.com/fulviofavilla/resume-radar
cd resume-radar

cp .env.example .env
# Edit .env with your API keys

docker compose up --build
```

API will be available at `http://localhost:8000`

### Run locally (dev)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys

uvicorn app.main:app --reload
```

---

## API Usage

### Analyze a resume

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@/path/to/your/resume.pdf" \
  -F "target_role=Data Engineer"
```

**Response:**
```json
{
  "job_id": "3f7a2c1d-...",
  "status": "processing",
  "message": "Analysis started. Poll /results/3f7a2c1d-... for updates."
}
```

### Get results

```bash
curl http://localhost:8000/results/3f7a2c1d-...
```

**Response:**
```json
{
  "job_id": "3f7a2c1d-...",
  "status": "completed",
  "resume_profile": {
    "skills": ["Python", "SQL", "Apache Airflow", "AWS"],
    "seniority": "mid",
    "summary": "Data Engineer with 2 years experience..."
  },
  "jobs_analyzed": 5,
  "gap_analysis": {
    "missing_skills": ["dbt", "Kubernetes", "Terraform"],
    "keyword_gaps": ["data lakehouse", "medallion architecture"],
    "strengths": ["Python", "pipeline orchestration", "cloud platforms"]
  },
  "recommendations": [
    "Add dbt to your stack — appears in 4/5 top matching jobs",
    "Kubernetes basics would unlock senior roles ($30-50/hr range)",
    "Your Airflow experience is a strong differentiator — highlight it more"
  ]
}
```

### Health check

```bash
curl http://localhost:8000/health
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FastAPI Layer                     │
│         POST /analyze    GET /results/{id}           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  LangGraph Agent                     │
│                                                      │
│  [parse_resume] → [search_jobs] → [embed_and_match]  │
│                                        │             │
│                               [generate_report]      │
└──────────────────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   [ChromaDB]    [RemoteOK API]  [Adzuna API]
   Vector Store   Job Search      Job Search
```

---

## Project Structure

```
resume-radar/
├── app/
│   ├── main.py              # FastAPI app + endpoints
│   ├── agent.py             # LangGraph agent definition
│   ├── nodes/
│   │   ├── parse_resume.py  # PDF parsing + LLM extraction
│   │   ├── search_jobs.py   # Job search tools
│   │   ├── embed_match.py   # RAG + semantic matching
│   │   └── generate_report.py  # Final report generation
│   ├── tools/
│   │   ├── remoteok.py      # RemoteOK API client
│   │   └── adzuna.py        # Adzuna API client
│   ├── models.py            # Pydantic models
│   └── config.py            # Settings via pydantic-settings
├── tests/
│   └── test_agent.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Roadmap

- [x] MVP: PDF → Job Search → Gap Analysis → Report
- [ ] ChromaDB semantic matching (replacing keyword matching)
- [ ] Frontend UI (React or simple HTML)
- [ ] Adzuna integration (broader job coverage)
- [ ] Course recommendations for identified gaps
- [ ] Resume improvement suggestions (rewrite weak bullet points)
- [ ] Multi-language support

---

## Contributing

PRs welcome. Open an issue first for major changes.

---

## License

MIT
