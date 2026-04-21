"""
Dense Vector 검색 모듈 - Numpy 기반
ChromaDB 대신 .npy 파일 + numpy 행렬 곱으로 코사인 유사도 검색합니다.

비대칭 임베딩:
  - 색인: solar-embedding-1-large-passage
  - 검색: solar-embedding-1-large-query

파일:
  index/embeddings.npy  - float16, shape=(N, 4096)
  index/embed_ids.json  - chunk_id 리스트
"""
import sys
import json
from typing import Dict, Any, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import config

IDS_PATH   = config.INDEX_DIR / "embed_ids.json"
EMBED_PATH = config.INDEX_DIR / "embeddings.npy"


# ── 임베딩 API 함수 ────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    text = text.strip()
    return text[:8000] if text else "내용 없음"


def _get_upstage_client():
    from openai import OpenAI
    return OpenAI(
        api_key=config.UPSTAGE_API_KEY,
        base_url="https://api.upstage.ai/v1",
    )


def embed_passages(texts: List[str]) -> List[List[float]]:
    """문서(passage) 임베딩 - 색인용 (배치)"""
    client = _get_upstage_client()
    all_embeddings = []
    for i in range(0, len(texts), 50):
        batch = [_clean_text(t) for t in texts[i:i+50]]
        try:
            resp = client.embeddings.create(
                model="solar-embedding-1-large-passage", input=batch
            )
            all_embeddings.extend([item.embedding for item in resp.data])
        except Exception as e:
            print(f"  [배치 오류] {e} → 단건 재시도")
            for text in batch:
                try:
                    resp = client.embeddings.create(
                        model="solar-embedding-1-large-passage", input=text
                    )
                    all_embeddings.append(resp.data[0].embedding)
                except Exception:
                    all_embeddings.append([0.0] * 4096)
    return all_embeddings


def embed_query(query: str) -> List[float]:
    """쿼리 임베딩 - 검색용"""
    client = _get_upstage_client()
    resp = client.embeddings.create(
        model="solar-embedding-1-large-query",
        input=_clean_text(query),
    )
    return resp.data[0].embedding


# ── DenseRetriever ─────────────────────────────────────────────────────────

class DenseRetriever:
    def __init__(self):
        self.embeddings: np.ndarray | None = None  # float32, (N, D)
        self.chunk_ids: List[str] = []

    def load(self) -> None:
        """저장된 Numpy 임베딩을 메모리에 로드합니다."""
        with open(IDS_PATH, encoding="utf-8") as f:
            self.chunk_ids = json.load(f)

        arr = np.load(str(EMBED_PATH))  # float16 저장
        self.embeddings = arr.astype(np.float32)  # 연산은 float32로

        # L2 정규화 (코사인 유사도 = 정규화 벡터 내적)
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-9, norms)
        self.embeddings = self.embeddings / norms

        print(f"[Dense] 로드 완료: {len(self.chunk_ids)}개 청크, shape={self.embeddings.shape}")

    def search(
        self,
        query: str,
        top_k: int = config.DENSE_TOP_K,
    ) -> List[Tuple[str, float]]:
        """
        쿼리를 임베딩하고 코사인 유사도 기반 상위 top_k를 반환합니다.

        Returns:
            [(chunk_id, score), ...]  내림차순
        """
        if self.embeddings is None:
            raise RuntimeError("임베딩이 로드되지 않았습니다. load()를 먼저 호출하세요.")

        # 쿼리 임베딩 (query 모델)
        q_vec = np.array(embed_query(query), dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        # 행렬 내적 → 코사인 유사도
        scores = self.embeddings @ q_vec  # (N,)

        # 상위 top_k 선택
        top_indices = np.argpartition(scores, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [(self.chunk_ids[i], float(scores[i])) for i in top_indices]

    def is_built(self) -> bool:
        """임베딩 파일이 존재하는지 확인합니다."""
        return IDS_PATH.exists() and EMBED_PATH.exists()


# ── 싱글턴 ─────────────────────────────────────────────────────────────────

_retriever: DenseRetriever | None = None


def get_retriever() -> DenseRetriever:
    global _retriever
    if _retriever is None:
        _retriever = DenseRetriever()
        if _retriever.is_built():
            _retriever.load()
        else:
            raise RuntimeError(
                "Dense 인덱스가 없습니다. build_numpy_index.py를 먼저 실행하세요."
            )
    return _retriever
