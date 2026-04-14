from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # Adzuna (free tier — https://developer.adzuna.com/)
    adzuna_app_id: str = ""
    adzuna_api_key: str = ""
    adzuna_country: str = "us"

    # ChromaDB — host points to the Docker service name
    chroma_host: str = "vectordb"
    chroma_port: int = 8000
    chroma_collection_name: str = "job_postings"

    # Agent
    max_jobs_to_fetch: int = 10
    top_jobs_for_analysis: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
