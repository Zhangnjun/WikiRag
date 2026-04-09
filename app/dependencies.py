from __future__ import annotations

from functools import lru_cache

from app.clients.internal_ai import InternalAIClient
from app.clients.internal_embedding import InternalEmbeddingClient
from app.config import get_settings
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.rag_repository import RAGRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.sqlite import SQLiteRepository
from app.services.chunk_service import ChunkService
from app.services.classifier import DocumentClassifier
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_service import KnowledgeService
from app.services.normalize_service import KnowledgeNormalizeService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService
from app.services.source_service import SourceService
from app.services.vector_search_service import VectorSearchService
from app.services.wiki_service import WikiService

settings = get_settings()


@lru_cache(maxsize=1)
def get_sqlite_repository() -> SQLiteRepository:
    return SQLiteRepository(settings.sqlite_abspath)


@lru_cache(maxsize=1)
def get_source_repository() -> SourceRepository:
    return SourceRepository(get_sqlite_repository())


@lru_cache(maxsize=1)
def get_knowledge_repository() -> KnowledgeRepository:
    return KnowledgeRepository(get_sqlite_repository())


@lru_cache(maxsize=1)
def get_chunk_repository() -> ChunkRepository:
    return ChunkRepository(get_sqlite_repository())


@lru_cache(maxsize=1)
def get_rag_repository() -> RAGRepository:
    return RAGRepository(get_sqlite_repository())


@lru_cache(maxsize=1)
def get_wiki_service() -> WikiService:
    return WikiService(settings.wiki)


@lru_cache(maxsize=1)
def get_internal_ai_client() -> InternalAIClient:
    return InternalAIClient(settings.ai)


@lru_cache(maxsize=1)
def get_internal_embedding_client() -> InternalEmbeddingClient:
    return InternalEmbeddingClient(settings.ai)


@lru_cache(maxsize=1)
def get_classifier() -> DocumentClassifier:
    return DocumentClassifier()


@lru_cache(maxsize=1)
def get_normalize_service() -> KnowledgeNormalizeService:
    client = get_internal_ai_client()
    llm_agent = None
    if client.is_enabled():
        from app.agents.llm_normalize_agent import LLMNormalizeAgent

        llm_agent = LLMNormalizeAgent(client)
    return KnowledgeNormalizeService(get_classifier(), llm_agent)


@lru_cache(maxsize=1)
def get_source_service() -> SourceService:
    return SourceService(get_source_repository(), get_wiki_service())


@lru_cache(maxsize=1)
def get_chunk_service() -> ChunkService:
    return ChunkService(get_chunk_repository())


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(get_internal_embedding_client(), get_chunk_repository(), settings.rag)


@lru_cache(maxsize=1)
def get_vector_search_service() -> VectorSearchService:
    return VectorSearchService(get_internal_embedding_client(), get_chunk_repository(), settings.rag)


@lru_cache(maxsize=1)
def get_retrieval_service() -> RetrievalService:
    return RetrievalService(get_chunk_repository(), get_vector_search_service())


@lru_cache(maxsize=1)
def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService(
        get_knowledge_repository(),
        get_source_repository(),
        get_normalize_service(),
        get_chunk_service(),
        get_embedding_service(),
    )


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    return RAGService(get_retrieval_service(), get_rag_repository(), get_internal_ai_client(), settings.rag)
