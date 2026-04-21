"""
IssueTrace RAG 전체 파이프라인
모든 모듈을 통합하여 질문 → 청크 ID 5개 + 답변을 반환합니다.

흐름:
    질문 → [쟁점 추출] → [Hybrid Retrieval] → [Reranker] → [Generator]
               ↓                   ↓                ↓             ↓
           확장 쿼리       BM25 + Dense + RRF    Top-5 재정렬    근거 답변
"""
import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any

sys.stdout.reconfigure(encoding="utf-8")

import config
from corpus import load_corpus
from bm25_retriever import BM25Retriever
from dense_retriever import DenseRetriever
from hybrid_retriever import HybridRetriever
from reranker import get_reranker, Reranker
from generator import generate_answer


# ── 결과 구조 ─────────────────────────────────────────────────────────────

@dataclass
class RAGResult:
    question: str
    chunk_ids: List[str]           # 정확히 5개
    answer: str
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "chunk_ids": self.chunk_ids,
            "answer": self.answer,
            "elapsed_sec": round(self.elapsed_sec, 2),
        }


# ── 쟁점 추출 (질의 확장) ─────────────────────────────────────────────────

def expand_query(query: str) -> str:
    """
    공정거래 도메인 쟁점 키워드를 추가하여 검색 친화적 질의를 생성합니다.

    LLM 없이 규칙 기반으로 동작하여 레이턴시를 줄입니다.
    """
    # 공정거래 도메인 키워드 사전
    keyword_map = {
        "담합": ["부당한 공동행위", "가격 담합", "입찰 담합", "시장 분할"],
        "과징금": ["과징금 부과", "과징금 금액", "제재"],
        "시정명령": ["시정명령", "금지명령", "조치"],
        "지위남용": ["시장지배적 지위남용", "거래상 지위남용", "우월적 지위"],
        "불공정": ["불공정거래행위", "불공정 하도급", "대규모유통업"],
        "사업자단체": ["사업자단체금지행위", "가격 협정", "경쟁 제한"],
        "기업결합": ["기업결합 신고", "합병", "인수"],
        "하도급": ["하도급법", "불공정하도급", "원사업자"],
        "전자상거래": ["전자상거래소비자보호법", "통신판매"],
        "위반": ["법위반행위", "위반 행위", "위반사실"],
        "제재": ["시정명령", "과징금", "경고"],
    }

    expanded_terms = [query]

    for keyword, expansions in keyword_map.items():
        if keyword in query:
            expanded_terms.extend(expansions)

    # 기업명이 포함된 경우 "의결서" 관련 용어 추가
    legal_suffixes = ["주식회사", "(주)", "㈜", "협회", "조합", "위원회"]
    for suffix in legal_suffixes:
        if suffix in query:
            expanded_terms.extend(["의결서", "피심인", "위반행위"])
            break

    return " ".join(expanded_terms)


# ── 파이프라인 ─────────────────────────────────────────────────────────────

class RAGPipeline:
    """IssueTrace RAG 메인 파이프라인"""

    def __init__(self):
        self.corpus: Dict[str, Dict[str, Any]] | None = None
        self.bm25: BM25Retriever | None = None
        self.dense: DenseRetriever | None = None
        self.hybrid: HybridRetriever | None = None
        self.reranker: Reranker | None = None
        self._initialized = False

    def initialize(self) -> None:
        """모든 모듈을 로드합니다 (서버 시작 시 1회 실행)."""
        if self._initialized:
            return

        print("[Pipeline] 초기화 시작...")
        t0 = time.time()

        # 1. 코퍼스 로드
        self.corpus = load_corpus()

        # 2. BM25 인덱스 로드
        self.bm25 = BM25Retriever()
        self.bm25.load()

        # 3. Dense 인덱스 로드 (없으면 또는 OFFLINE_MODE면 BM25만 사용)
        self.dense = DenseRetriever()
        self._use_dense = False
        if config.OFFLINE_MODE:
            print("[Pipeline] OFFLINE_MODE=true → BM25 단독 모드 (Dense 스킵)")
        else:
            try:
                if self.dense.is_built():
                    self.dense.load()
                    self._use_dense = True
                else:
                    print("[Pipeline] Dense 인덱스 없음 → BM25 단독 모드")
            except Exception as e:
                print(f"[Pipeline] Dense 로드 실패: {e} → BM25 단독 모드")

        # 4. Hybrid Retriever 구성
        if self._use_dense:
            self.hybrid = HybridRetriever(self.bm25, self.dense, self.corpus)
        else:
            self.hybrid = _BM25OnlyRetriever(self.bm25, self.corpus)

        # 5. Reranker 로드
        self.reranker = get_reranker()

        self._initialized = True
        mode = "Hybrid (BM25+Dense)" if self._use_dense else "BM25 단독"
        print(f"[Pipeline] 초기화 완료 [{mode}] ({time.time() - t0:.1f}s)")

    def run(self, question: str) -> RAGResult:
        """
        질문에 대해 RAG 파이프라인을 실행합니다.

        Returns:
            RAGResult (chunk_ids 5개 + answer 포함)
        """
        if not self._initialized:
            self.initialize()

        t_start = time.time()

        # Step 1: 쟁점 추출 / 질의 확장
        expanded_query = expand_query(question)

        # Step 2: Hybrid Retrieval → 후보 청크 확보
        # reranker가 있을 때는 더 많은 후보 확보
        candidate_k = config.FINAL_TOP_K * 3 if config.RERANKER != "none" else config.FINAL_TOP_K
        chunks = self.hybrid.get_chunks_with_text(expanded_query, top_k=candidate_k)

        # Step 3: Reranker → 최종 5개 선정
        final_chunks = self.reranker.rerank(question, chunks, top_k=config.FINAL_TOP_K)

        # Step 4: 정확히 5개 보장
        final_chunks = _ensure_five(final_chunks, self.hybrid, expanded_query, self.corpus)
        chunk_ids = [c["chunk_id"] for c in final_chunks]

        # Step 5: 답변 생성
        answer = generate_answer(question, final_chunks)

        elapsed = time.time() - t_start
        return RAGResult(
            question=question,
            chunk_ids=chunk_ids,
            answer=answer,
            retrieved_chunks=final_chunks,
            elapsed_sec=elapsed,
        )


class _BM25OnlyRetriever:
    """Dense 인덱스 없이 BM25만으로 동작하는 폴백 Retriever"""

    def __init__(self, bm25: BM25Retriever, corpus: Dict[str, Dict[str, Any]]):
        self.bm25 = bm25
        self.corpus = corpus
        self._valid_ids = set(corpus.keys())

    def get_chunk_ids(self, query: str, top_k: int = config.FINAL_TOP_K) -> List[str]:
        results = self.bm25.search(query, top_k=top_k)
        return [cid for cid, _ in results if cid in self._valid_ids][:top_k]

    def get_chunks_with_text(
        self, query: str, top_k: int = config.FINAL_TOP_K
    ) -> List[Dict[str, Any]]:
        ids = self.get_chunk_ids(query, top_k=top_k)
        return [
            {
                "chunk_id": cid,
                "text": self.corpus[cid]["text"],
                "metadata": self.corpus[cid]["metadata"],
            }
            for cid in ids
            if cid in self.corpus
        ]


def _ensure_five(
    chunks: List[Dict[str, Any]],
    hybrid: HybridRetriever,
    query: str,
    corpus: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """청크가 5개 미만이면 추가로 채웁니다."""
    if len(chunks) >= config.FINAL_TOP_K:
        return chunks[: config.FINAL_TOP_K]

    existing_ids = {c["chunk_id"] for c in chunks}
    extra = hybrid.get_chunk_ids(query, top_k=config.FINAL_TOP_K * 4)

    for cid in extra:
        if cid not in existing_ids and cid in corpus:
            chunks.append({
                "chunk_id": cid,
                "text": corpus[cid]["text"],
                "metadata": corpus[cid]["metadata"],
            })
            existing_ids.add(cid)
        if len(chunks) == config.FINAL_TOP_K:
            break

    return chunks[: config.FINAL_TOP_K]


# ── 싱글턴 ─────────────────────────────────────────────────────────────────

_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
        _pipeline.initialize()
    return _pipeline


# ── CLI 테스트 ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "BGF리테일의 판매촉진비용 위반 행위는 무엇인가요?"
    print(f"\n질문: {query}")
    print("=" * 60)

    pipeline = get_pipeline()
    result = pipeline.run(query)

    print(f"\n[검색된 청크 IDs] ({result.elapsed_sec:.2f}s)")
    for i, cid in enumerate(result.chunk_ids, 1):
        print(f"  {i}. {cid}")

    print(f"\n[생성된 답변]")
    print(result.answer)
