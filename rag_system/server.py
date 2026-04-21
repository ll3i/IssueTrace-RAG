"""
IssueTrace RAG - FastAPI 서버

엔드포인트:
    POST /query   - 질문 → chunk_ids(5개) + answer 반환
    GET  /health  - 서버 상태 확인
    GET  /stats   - 코퍼스 통계

실행:
    python server.py
    또는
    uvicorn server:app --host 0.0.0.0 --port 8000
"""
import sys
import time
import logging
import os

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from pathlib import Path

import config
from pipeline import get_pipeline, RAGResult

STATIC_DIR = Path(__file__).parent / "static"


# ── 앱 초기화 ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 파이프라인 + 로컬 LLM을 초기화합니다."""
    logger.info("파이프라인 초기화 중...")
    try:
        get_pipeline()
        logger.info("파이프라인 초기화 완료")
    except Exception as e:
        logger.error(f"파이프라인 초기화 실패: {e}")
        raise

    # 오프라인 모드: 로컬 LLM을 서버 시작 시 미리 로드 (첫 요청 30초 초과 방지)
    if config.USE_LOCAL_LLM:
        logger.info("로컬 LLM 사전 로드 중...")
        try:
            from generator_local import preload
            import asyncio
            await asyncio.get_event_loop().run_in_executor(None, preload)
            logger.info("로컬 LLM 사전 로드 완료")
        except Exception as e:
            logger.error(f"로컬 LLM 사전 로드 실패: {e}")
            raise

    yield


app = FastAPI(
    title="IssueTrace RAG API",
    description="공정거래 의결서 기반 Hybrid RAG 질의응답 시스템",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── 스키마 ─────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="질문 텍스트")


class ChunkInfo(BaseModel):
    chunk_id: str
    text: str
    metadata: dict


class QueryResponse(BaseModel):
    question: str
    chunk_ids: list[str] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="관련 청크 ID 목록 (정확히 5개, 순서=랭킹)",
    )
    answer: str = Field(..., description="근거 기반 생성 답변")
    elapsed_sec: float = Field(..., description="처리 시간 (초)")
    retrieved_chunks: list[ChunkInfo] = Field(default_factory=list, description="검색된 청크 상세")


# ── 평가 서버 스키마 (/predict 엔드포인트) ──────────────────────────────────

class PredictRequest(BaseModel):
    id: str = Field(..., description="평가 질문 ID (예: eval_0001)")
    question: str = Field(..., min_length=1, max_length=500, description="질문 텍스트")


class PredictResponse(BaseModel):
    id: str
    retrieved_chunk_ids: list[str] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="관련 청크 ID 목록 (정확히 5개, 순서=랭킹)",
    )
    answer: str = Field(..., description="근거 기반 생성 답변")


class HealthResponse(BaseModel):
    status: str
    corpus_size: int
    embedding_provider: str
    generation_model: str
    reranker: str


class StatsResponse(BaseModel):
    total_chunks: int
    total_documents: int
    embedding_provider: str
    generation_model: str
    bm25_top_k: int
    dense_top_k: int
    rrf_k: int


# ── 엔드포인트 ─────────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    질문에 대해 RAG 파이프라인을 실행합니다.

    - chunk_ids: 관련도 순으로 정렬된 정확히 5개의 청크 ID
    - answer: 검색된 청크를 근거로 생성된 답변
    - elapsed_sec: 총 처리 시간 (30초 초과 시 0점 처리됨)
    """
    t_start = time.time()

    try:
        pipeline = get_pipeline()
        result: RAGResult = pipeline.run(request.question)
    except Exception as e:
        logger.error(f"파이프라인 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.time() - t_start

    # 안전 검증
    if len(result.chunk_ids) != 5:
        logger.warning(f"chunk_ids 수 이상: {len(result.chunk_ids)}")
        raise HTTPException(
            status_code=500,
            detail=f"chunk_ids가 5개가 아닙니다: {len(result.chunk_ids)}개"
        )

    if len(set(result.chunk_ids)) != 5:
        logger.warning(f"중복 chunk_id 감지: {result.chunk_ids}")
        raise HTTPException(status_code=500, detail="중복 chunk_id가 있습니다")

    if elapsed > 28:
        logger.warning(f"응답 지연 경고: {elapsed:.1f}s")

    logger.info(f"질문: {request.question[:50]}... | {elapsed:.2f}s")

    return QueryResponse(
        question=result.question,
        chunk_ids=result.chunk_ids,
        answer=result.answer,
        elapsed_sec=round(elapsed, 2),
        retrieved_chunks=[
            ChunkInfo(
                chunk_id=c["chunk_id"],
                text=c["text"],
                metadata=c["metadata"],
            )
            for c in result.retrieved_chunks
        ],
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """
    평가 서버용 엔드포인트.

    평가 서버가 POST /predict 로 질문을 전달하면
    retrieved_chunk_ids (5개) + answer 를 반환합니다.
    """
    t_start = time.time()

    try:
        pipeline = get_pipeline()
        result: RAGResult = pipeline.run(request.question)
    except Exception as e:
        logger.error(f"[predict] 파이프라인 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.time() - t_start

    if len(result.chunk_ids) != 5:
        raise HTTPException(
            status_code=500,
            detail=f"chunk_ids가 5개가 아닙니다: {len(result.chunk_ids)}개"
        )
    if len(set(result.chunk_ids)) != 5:
        raise HTTPException(status_code=500, detail="중복 chunk_id가 있습니다")

    if elapsed > 28:
        logger.warning(f"[predict] 응답 지연: {elapsed:.1f}s ({request.id})")

    logger.info(f"[predict] {request.id} | {request.question[:50]}... | {elapsed:.2f}s")

    return PredictResponse(
        id=request.id,
        retrieved_chunk_ids=result.chunk_ids,
        answer=result.answer,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """서버 상태를 반환합니다."""
    try:
        pipeline = get_pipeline()
        corpus_size = len(pipeline.corpus) if pipeline.corpus else 0
    except Exception:
        corpus_size = 0

    return HealthResponse(
        status="ok",
        corpus_size=corpus_size,
        embedding_provider=config.EMBEDDING_PROVIDER,
        generation_model=config.GENERATION_MODEL,
        reranker=config.RERANKER,
    )


@app.get("/stats", response_model=StatsResponse)
async def stats():
    """코퍼스 및 설정 통계를 반환합니다."""
    try:
        pipeline = get_pipeline()
        total_chunks = len(pipeline.corpus) if pipeline.corpus else 0
    except Exception:
        total_chunks = 0

    # 문서 수 = 고유한 doc_id 수
    total_docs = 0
    if get_pipeline()._initialized and get_pipeline().corpus:
        doc_ids = {v["metadata"].get("doc_id") for v in get_pipeline().corpus.values()}
        total_docs = len(doc_ids)

    return StatsResponse(
        total_chunks=total_chunks,
        total_documents=total_docs,
        embedding_provider=config.EMBEDDING_PROVIDER,
        generation_model=config.GENERATION_MODEL,
        bm25_top_k=config.BM25_TOP_K,
        dense_top_k=config.DENSE_TOP_K,
        rrf_k=config.RRF_K,
    )


# ── 실행 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
