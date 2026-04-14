"""
ChromaDB client — singleton for the app lifetime.

Architecture:
  The API container connects to the ChromaDB container (service name: vectordb)
  via HTTP. ChromaDB persists embeddings to a named Docker volume (chroma_data),
  so vectors survive container restarts.

Usage:
  from app.vector_store import get_collection
  collection = get_collection()
"""
from __future__ import annotations
import chromadb
from app.config import get_settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_client: Optional[chromadb.HttpClient] = None


def get_chroma_client() -> chromadb.HttpClient:
    """Return the shared ChromaDB HTTP client, creating it if needed."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        logger.info(f"ChromaDB client connected → {settings.chroma_host}:{settings.chroma_port}")
    return _client


def get_collection(collection_name: str | None = None) -> chromadb.Collection:
    """
    Return (or create) a ChromaDB collection.
    Uses get_or_create_collection so it's idempotent across restarts.
    """
    settings = get_settings()
    name = collection_name or settings.chroma_collection_name
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},  # cosine similarity for skill matching
    )
    logger.info(f"ChromaDB collection '{name}' ready")
    return collection
