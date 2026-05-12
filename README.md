# ResumeRadar

> AI-powered resume analyzer for tech roles. Upload your PDF, get matched against real remote job postings, surface skill gaps, get targeted rewrite suggestions, and download a formatted PDF report.

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
                    │ LLM embeddings +       │
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

**Prerequisites:** Docker · OpenAI API key (or a local LLM - see [Local LLM](#local-llm))

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

**Privacy note:** If you are using the OpenAI API, consider redacting personal details (name, email, phone, address) from your resume before uploading. OpenAI's API data is not used for model training by default - see their [Privacy Policy](https://openai.com/policies/privacy-policy) and [Terms of Use](https://openai.com/policies/terms-of-use) for details.

---

## Local LLM

ResumeRadar works with any OpenAI-compatible endpoint. To run without sending data to OpenAI, set these in `.env` instead of an API key:

```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_MODEL=llama3.1:8b
OPENAI_EMBEDDING_MODEL=nomic-embed-text
```

Tested with [Ollama](https://ollama.com). All Ollama models expose an OpenAI-compatible API, so any model works - better models produce more consistent output. Pull the required models first:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

If you change `OPENAI_EMBEDDING_MODEL`, run `docker compose down -v` first to clear the ChromaDB volume and avoid dimension mismatch errors.

**Linux only:** Ollama listens on `localhost` by default and is not reachable from inside Docker. Configure it to bind to the Docker gateway:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=172.17.0.1"
EOF
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

`172.17.0.1` is the default Docker gateway on most Linux systems. If the connection still fails, verify yours with `docker network inspect bridge | grep Gateway` and update accordingly.

---

## Output

```json
{
  "status": "completed",
  "resume_profile": {
    "skills": ["Python", "SQL", "AWS", "Apache Airflow", "Docker"],
    "inferred_skills": ["ETL pipelines", "CI/CD", "data governance"],
    "seniority": "mid",
    "years_of_experience": 2
  },
  "report": {
    "gap_analysis": {
      "match_score": 0.81,
      "strengths": ["Python", "SQL", "AWS"],
      "missing_skills": ["dbt", "Kafka"]
    },
    "recommendations": ["..."],
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

`embed_match` uses a two-pass approach: LLM extraction to get real required skills from job descriptions (not noisy job board tags), then embeddings + ChromaDB cosine similarity. This lifts `match_score` from ~0.1 (keyword overlap) to ~0.8 (semantic similarity). Falls back to keyword gap analysis if ChromaDB is unreachable.

`rewrite_resume` scores each bullet for market impact (1-10) and rewrites those scoring 6 or below, anchored to `missing_skills` or the union of required skills across top jobs for strong profiles.

---

## Known limitations

- Job search relies on RemoteOK and Adzuna - pool size varies by day. Providing a job description directly via the manual input tab bypasses this entirely.
- When running with a local LLM, the resume rewrite step may fail occasionally with smaller models (7-8B). The rest of the pipeline completes normally.

---

## License

MIT