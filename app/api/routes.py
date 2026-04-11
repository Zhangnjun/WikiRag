from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from openpyxl import Workbook

from app.api.deps import require_api_key
from app.core.exceptions import AppError
from app.dependencies import (
    get_internal_ai_client,
    get_internal_embedding_client,
    get_knowledge_service,
    get_rag_service,
    get_source_service,
    get_wiki_recommend_service,
    get_wiki_service,
)
from app.schemas.common import DeleteResponse, HealthResponse, MessageResponse
from app.schemas.knowledge import (
    KnowledgeDocumentResponse,
    KnowledgeListResponse,
    KnowledgeNormalizeRequest,
    KnowledgeRenormalizeRequest,
    KnowledgeSearchRequest,
    KnowledgeUpdateRequest,
)
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.schemas.source import (
    BatchImportRequest,
    BatchImportResponse,
    SourceImportRequest,
    SourceListResponse,
    SourceRecordResponse,
)
from app.schemas.wiki import (
    WikiRecommendExpandedRequest,
    WikiRecommendExpandedResponse,
    WikiRecommendRequest,
    WikiRecommendResponse,
    WikiSearchRequest,
    WikiSearchResponse,
)
from app.utils.trace import new_trace_id

router = APIRouter(dependencies=[Depends(require_api_key)])
public_router = APIRouter()


def _source_to_response(source) -> SourceRecordResponse:
    return SourceRecordResponse(**source.__dict__)


def _knowledge_to_response(document) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(**document.__dict__)


@public_router.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/rag-debug", status_code=307)


@public_router.get("/rag-debug", response_class=HTMLResponse, include_in_schema=False)
def rag_debug_page() -> HTMLResponse:
    html_path = Path(__file__).resolve().parents[1] / "static" / "rag_debug.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@router.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/api/ai/health")
def ai_health() -> dict:
    return {
        "chat": get_internal_ai_client().health_check(),
        "embedding": get_internal_embedding_client().health_check(),
    }


@router.post("/api/source/import", response_model=SourceRecordResponse)
def import_source(request: SourceImportRequest) -> SourceRecordResponse:
    record = get_source_service().import_source(request.dict(), trace_id=new_trace_id())
    return _source_to_response(record)


@router.post("/api/source/import/batch", response_model=BatchImportResponse)
def batch_import_source(request: BatchImportRequest) -> BatchImportResponse:
    results = get_source_service().batch_import(request.dict(), trace_id=new_trace_id())
    return BatchImportResponse(results=results)


@router.get("/api/source/list", response_model=SourceListResponse)
def list_sources(
    title: Optional[str] = None,
    source_type: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[str] = None,
    doc_type: Optional[str] = None,
    import_status: Optional[str] = None,
    normalize_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> SourceListResponse:
    items, total = get_source_service().list_sources(
        {
            "title": title,
            "source_type": source_type,
            "owner": owner,
            "tags": tags,
            "doc_type": doc_type,
            "import_status": import_status,
            "normalize_status": normalize_status,
        },
        page,
        page_size,
    )
    return SourceListResponse(
        items=[_source_to_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/api/source/{source_id}", response_model=SourceRecordResponse)
def get_source(source_id: str) -> SourceRecordResponse:
    return _source_to_response(get_source_service().get_source(source_id))


@router.delete("/api/source/{source_id}", response_model=DeleteResponse)
def delete_source(source_id: str) -> DeleteResponse:
    result = get_source_service().delete_source(source_id, trace_id=new_trace_id())
    return DeleteResponse(**result)


@router.post("/api/wiki/search", response_model=WikiSearchResponse)
def wiki_search(request: WikiSearchRequest) -> WikiSearchResponse:
    payload = get_wiki_service().normalize_search_results(
        request.search_query,
        page=request.page,
        page_size=request.page_size,
        cookie_override=request.cookie,
    )
    return WikiSearchResponse(**payload)


@router.post("/api/wiki/recommend", response_model=WikiRecommendResponse)
def wiki_recommend(request: WikiRecommendRequest) -> WikiRecommendResponse:
    payload = get_wiki_recommend_service().recommend(
        profile_text=request.profile_text,
        focus_topics=request.focus_topics,
        page_size=request.page_size,
        max_queries=request.max_queries,
        cookie_override=request.cookie,
    )
    return WikiRecommendResponse(**payload)


@router.post("/api/wiki/recommend/expanded", response_model=WikiRecommendExpandedResponse)
def wiki_recommend_expanded(request: WikiRecommendExpandedRequest) -> WikiRecommendExpandedResponse:
    payload = get_wiki_recommend_service().recommend_expanded(
        profile_text=request.profile_text,
        focus_topics=request.focus_topics,
        page_size=request.page_size,
        max_queries=request.max_queries,
        pages_per_query=request.pages_per_query,
        min_score=request.min_score,
        cookie_override=request.cookie,
        trace_id=new_trace_id(),
    )
    return WikiRecommendExpandedResponse(**payload)


@router.post("/api/wiki/recommend/expanded/export", include_in_schema=True)
def wiki_recommend_expanded_export(request: WikiRecommendExpandedRequest) -> FileResponse:
    payload = get_wiki_recommend_service().recommend_expanded(
        profile_text=request.profile_text,
        focus_topics=request.focus_topics,
        page_size=request.page_size,
        max_queries=request.max_queries,
        pages_per_query=request.pages_per_query,
        min_score=request.min_score,
        cookie_override=request.cookie,
        trace_id=new_trace_id(),
    )

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "summary"
    summary_sheet.append(["detected_doc_type", payload["detected_doc_type"]])
    summary_sheet.append(["query_candidates", " | ".join(payload["query_candidates"])])
    summary = payload["summary"]
    summary_sheet.append(["total_candidates", summary["total_candidates"]])
    summary_sheet.append(["deduped_candidates", summary["deduped_candidates"]])
    summary_sheet.append(["high_relevance", summary["high_relevance"]])
    summary_sheet.append(["medium_relevance", summary["medium_relevance"]])
    summary_sheet.append(["low_relevance", summary["low_relevance"]])

    items_sheet = workbook.create_sheet("recommendations")
    items_sheet.append(
        [
            "score",
            "title",
            "sn",
            "url",
            "reason",
            "matched_terms",
            "query_used",
            "skill_feasibility",
            "skill_reason",
            "domain_id",
            "domain_title",
            "kanban_id",
            "kanban_title",
            "summary",
            "updated_at",
            "created_at",
        ]
    )
    for item in payload["items"]:
        items_sheet.append(
            [
                item.get("score", 0),
                item.get("title", ""),
                item.get("sn", ""),
                item.get("url", ""),
                item.get("reason", ""),
                " | ".join(item.get("matched_terms", [])),
                item.get("query_used", ""),
                item.get("skill_feasibility", ""),
                item.get("skill_reason", ""),
                item.get("domain_id"),
                item.get("domain_title", ""),
                item.get("kanban_id"),
                item.get("kanban_title", ""),
                item.get("summary", ""),
                item.get("updated_at", ""),
                item.get("created_at", ""),
            ]
        )

    with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        workbook.save(tmp.name)
        export_path = tmp.name

    filename = "wiki_recommendations_%s.xlsx" % datetime.now().strftime("%Y%m%d_%H%M%S")
    return FileResponse(
        path=export_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/api/knowledge/normalize", response_model=KnowledgeDocumentResponse)
def normalize_knowledge(request: KnowledgeNormalizeRequest) -> KnowledgeDocumentResponse:
    source_service = get_source_service()
    knowledge_service = get_knowledge_service()

    if request.source_id:
        source = source_service.get_source(request.source_id)
    else:
        inline = request.source
        if not inline:
            raise AppError("source_id or source must be provided")
        source = source_service.import_source(inline.dict())
    document = knowledge_service.normalize_from_source(source, request.use_ai, request.doc_type, trace_id=new_trace_id())
    return _knowledge_to_response(document)


@router.get("/api/knowledge/list", response_model=KnowledgeListResponse)
def list_knowledge(
    doc_type: Optional[str] = None,
    knowledge_domain: Optional[str] = None,
    product_line: Optional[str] = None,
    role: Optional[str] = None,
    keyword: Optional[str] = None,
    is_archived: Optional[bool] = Query(default=None),
) -> KnowledgeListResponse:
    items = get_knowledge_service().list_documents(
        {
            "doc_type": doc_type,
            "knowledge_domain": knowledge_domain,
            "product_line": product_line,
            "role": role,
            "keyword": keyword,
            "is_archived": is_archived,
        }
    )
    return KnowledgeListResponse(items=[_knowledge_to_response(item) for item in items], total=len(items))


@router.get("/api/knowledge/{doc_id}", response_model=KnowledgeDocumentResponse)
def get_knowledge(doc_id: str) -> KnowledgeDocumentResponse:
    document = get_knowledge_service().get_document(doc_id)
    return _knowledge_to_response(document)


@router.put("/api/knowledge/{doc_id}", response_model=KnowledgeDocumentResponse)
def update_knowledge(doc_id: str, request: KnowledgeUpdateRequest) -> KnowledgeDocumentResponse:
    updates = {key: value for key, value in request.dict().items() if value is not None}
    document = get_knowledge_service().update_document(doc_id, updates)
    return _knowledge_to_response(document)


@router.post("/api/knowledge/{doc_id}/archive", response_model=MessageResponse)
def archive_knowledge(doc_id: str) -> MessageResponse:
    get_knowledge_service().archive_document(doc_id)
    return MessageResponse(message=f"Document archived: {doc_id}")


@router.post("/api/knowledge/search", response_model=KnowledgeListResponse)
def search_knowledge(request: KnowledgeSearchRequest) -> KnowledgeListResponse:
    items = get_knowledge_service().search_documents(
        request.query,
        {
            "doc_type": request.doc_type,
            "product_line": request.product_line,
            "role": request.role,
            "keyword": request.keyword,
        },
    )
    return KnowledgeListResponse(items=[_knowledge_to_response(item) for item in items], total=len(items))


@router.post("/api/knowledge/{doc_id}/renormalize", response_model=KnowledgeDocumentResponse)
def renormalize_knowledge(doc_id: str, request: KnowledgeRenormalizeRequest) -> KnowledgeDocumentResponse:
    document = get_knowledge_service().renormalize_document(
        doc_id,
        use_ai=request.use_ai,
        doc_type=request.doc_type,
        trace_id=new_trace_id(),
    )
    return _knowledge_to_response(document)


@router.post("/api/rag/query", response_model=RAGQueryResponse)
def rag_query(request: RAGQueryRequest) -> RAGQueryResponse:
    response = get_rag_service().query(
        query=request.query,
        top_k=request.top_k,
        use_rerank=request.use_rerank,
        use_ai=request.use_ai,
        filters=request.filters.dict(),
        debug=request.debug,
        session_id=request.session_id,
        trace_id=new_trace_id(),
    )
    return RAGQueryResponse(**response)
