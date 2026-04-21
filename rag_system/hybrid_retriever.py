"""
Hybrid Retrieval 모듈
BM25(Sparse) + Dense(Vector)를 RRF(Reciprocal Rank Fusion)로 결합합니다.

RRF 공식:
    score(d) = Σ 1 / (k + rank(d, L_i))
    k = 60 (논문 권장값, 하위 랭크 영향력 조절)
"""
import sys
from typing import Dict, Any, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")

import config
from bm25_retriever import BM25Retriever
from dense_retriever import DenseRetriever


def reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[str, float]]],
    k: int = config.RRF_K,
) -> List[Tuple[str, float]]:
    """
    여러 랭킹 결과를 RRF로 통합합니다.

    Args:
        ranked_lists: [(chunk_id, score), ...] 형태의 랭킹 목록들
        k: RRF 파라미터 (클수록 하위 랭크 영향 감소)

    Returns:
        [(chunk_id, rrf_score), ...]  내림차순
    """
    rrf_scores: Dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, (chunk_id, _) in enumerate(ranked_list):
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)


class HybridRetriever:
    def __init__(
        self,
        bm25: BM25Retriever,
        dense: DenseRetriever,
        corpus: Dict[str, Dict[str, Any]],
    ):
        self.bm25 = bm25
        self.dense = dense
        self.corpus = corpus
        # 유효한 chunk_id 집합 (안전 검증용)
        self._valid_ids = set(corpus.keys())

    def search(
        self,
        query: str,
        top_k: int = config.FINAL_TOP_K,
        bm25_k: int = config.BM25_TOP_K,
        dense_k: int = config.DENSE_TOP_K,
        rrf_k: int = config.RRF_K,
    ) -> List[Tuple[str, float]]:
        """
        Hybrid 검색 수행 후 상위 top_k 청크를 반환합니다.

        Returns:
            [(chunk_id, rrf_score), ...]  내림차순, 길이 = top_k
        """
        # 1. BM25 검색
        bm25_results = self.bm25.search(query, top_k=bm25_k)

        # 2. Dense 검색
        dense_results = self.dense.search(query, top_k=dense_k)

        # 3. RRF 통합
        merged = reciprocal_rank_fusion([bm25_results, dense_results], k=rrf_k)

        # 4. 유효한 chunk_id만 필터 + 상위 top_k 선택
        valid = [(cid, score) for cid, score in merged if cid in self._valid_ids]
        return valid[:top_k]

    def get_chunk_ids(self, query: str, top_k: int = config.FINAL_TOP_K) -> List[str]:
        """최종 반환할 chunk_id 목록 (정확히 top_k개)을 반환합니다."""
        results = self.search(query, top_k=top_k)
        ids = [cid for cid, _ in results]

        # 부족하면 BM25 fallback으로 채움
        if len(ids) < top_k:
            bm25_extra = self.bm25.search(query, top_k=top_k * 3)
            for cid, _ in bm25_extra:
                if cid not in ids and cid in self._valid_ids:
                    ids.append(cid)
                if len(ids) == top_k:
                    break

        return ids[:top_k]

    def get_chunks_with_text(
        self, query: str, top_k: int = config.FINAL_TOP_K
    ) -> List[Dict[str, Any]]:
        """chunk_id + 텍스트 + 메타를 함께 반환합니다."""
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
