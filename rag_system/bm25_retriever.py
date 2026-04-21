"""
BM25 Sparse 검색 모듈
한국어 특성을 고려한 토크나이저와 rank-bm25 라이브러리를 사용합니다.

토크나이저 전략:
  - 공백 분리 토큰 + 문자 2-gram 결합
  - konlpy 없이도 법률 용어의 부분 매칭을 처리
"""
import pickle
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")

from rank_bm25 import BM25Okapi
import config


# ── 토크나이저 ──────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """불필요한 공백·특수문자를 정규화합니다."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s가-힣a-zA-Z0-9]", " ", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    """
    공백 분리 + 한국어 2-gram 토크나이징
    예: "시장지배적 지위남용" → ["시장지배적", "지위남용", "시장지", "장지배", "지배적", "지위남", "위남용"]
    """
    cleaned = _clean(text)
    words = cleaned.split()

    tokens = list(words)  # 단어 단위 토큰

    # 한국어 2-gram (길이 2 이상 단어에만 적용)
    for word in words:
        if len(word) >= 2:
            for i in range(len(word) - 1):
                tokens.append(word[i : i + 2])

    return tokens


# ── BM25 인덱스 ────────────────────────────────────────────────────────────

class BM25Retriever:
    def __init__(self):
        self.bm25: BM25Okapi | None = None
        self.chunk_ids: List[str] = []
        self.corpus_texts: List[str] = []

    def build(self, corpus: Dict[str, Dict[str, Any]]) -> None:
        """코퍼스로부터 BM25 인덱스를 구성합니다."""
        print("[BM25] 인덱스 구축 중...")
        self.chunk_ids = list(corpus.keys())
        self.corpus_texts = [v["text"] for v in corpus.values()]

        tokenized = [tokenize(text) for text in self.corpus_texts]
        self.bm25 = BM25Okapi(tokenized)
        print(f"[BM25] {len(self.chunk_ids)}개 청크 인덱싱 완료")

    def save(self, path: Path = config.BM25_INDEX_PATH) -> None:
        """인덱스를 파일로 저장합니다."""
        with open(path, "wb") as f:
            pickle.dump({
                "bm25": self.bm25,
                "chunk_ids": self.chunk_ids,
                "corpus_texts": self.corpus_texts,
            }, f)
        print(f"[BM25] 저장 완료: {path}")

    def load(self, path: Path = config.BM25_INDEX_PATH) -> None:
        """저장된 인덱스를 로드합니다."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.bm25 = data["bm25"]
        self.chunk_ids = data["chunk_ids"]
        self.corpus_texts = data["corpus_texts"]
        print(f"[BM25] 로드 완료: {len(self.chunk_ids)}개 청크")

    def search(
        self,
        query: str,
        top_k: int = config.BM25_TOP_K,
        corpus: Dict[str, Dict[str, Any]] | None = None,
    ) -> List[Tuple[str, float]]:
        """
        쿼리에 대해 BM25 검색을 수행합니다.

        Returns:
            [(chunk_id, score), ...]  점수 내림차순
        """
        if self.bm25 is None:
            raise RuntimeError("인덱스가 로드되지 않았습니다. build() 또는 load()를 먼저 호출하세요.")

        query_tokens = tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        # 상위 top_k 선택
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(self.chunk_ids[i], float(scores[i])) for i in top_indices]


# ── 싱글턴 ─────────────────────────────────────────────────────────────────

_retriever: BM25Retriever | None = None


def get_retriever() -> BM25Retriever:
    global _retriever
    if _retriever is None:
        _retriever = BM25Retriever()
        if config.BM25_INDEX_PATH.exists():
            _retriever.load()
        else:
            raise RuntimeError(
                "BM25 인덱스가 없습니다. build_index.py를 먼저 실행하세요."
            )
    return _retriever


if __name__ == "__main__":
    # 빠른 동작 테스트
    sample_corpus = {
        "CH-001": {"text": "시장지배적 사업자의 지위남용행위에 대한 제재", "metadata": {}},
        "CH-002": {"text": "불공정거래행위 및 부당한 공동행위(담합)", "metadata": {}},
        "CH-003": {"text": "과징금 부과 및 시정명령 조치", "metadata": {}},
    }
    r = BM25Retriever()
    r.build(sample_corpus)
    results = r.search("담합 과징금", top_k=3)
    print("검색 결과:", results)
