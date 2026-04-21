"""
재정렬(Reranker) 모듈
Hybrid Retrieval 후보를 질의와의 관련성 기준으로 재정렬합니다.

지원 모드 (config.RERANKER):
  - "upstage" : Upstage Rerank API (solar-rerank-1) 사용
  - "none"    : 재정렬 없이 그대로 반환 (기본값)

향후 확장:
  - "cross_encoder" : 로컬 cross-encoder 모델
"""
import sys
from typing import List, Dict, Any

sys.stdout.reconfigure(encoding="utf-8")

import config


class Reranker:
    """재정렬 모듈 베이스 클래스"""

    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = config.FINAL_TOP_K,
    ) -> List[Dict[str, Any]]:
        """
        Args:
            query: 사용자 질문
            chunks: [{"chunk_id", "text", "metadata"}, ...] (이미 top-K 후보)
            top_k: 최종 반환 수 (반드시 5)

        Returns:
            재정렬된 chunks[:top_k]
        """
        raise NotImplementedError


class NoReranker(Reranker):
    """재정렬 없이 입력 순서 그대로 반환합니다."""

    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = config.FINAL_TOP_K,
    ) -> List[Dict[str, Any]]:
        return chunks[:top_k]


class UpstageReranker(Reranker):
    """Upstage Rerank API를 이용한 재정렬"""

    def __init__(self):
        if not config.UPSTAGE_API_KEY:
            raise ValueError("UPSTAGE_API_KEY가 설정되지 않았습니다.")
        from openai import OpenAI
        self.client = OpenAI(
            api_key=config.UPSTAGE_API_KEY,
            base_url="https://api.upstage.ai/v1",
        )

    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = config.FINAL_TOP_K,
    ) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        # Upstage Rerank API 호출
        documents = [c["text"][:2000] for c in chunks]  # 길이 제한

        try:
            response = self.client.post(
                "/information-extraction/rerank",
                body={
                    "model": "solar-rerank-1",
                    "query": query,
                    "documents": documents,
                    "top_n": min(top_k, len(documents)),
                },
            )
            # 응답에서 재정렬된 인덱스 추출
            results = response.get("results", [])
            reranked = [chunks[r["index"]] for r in results]
        except Exception as e:
            print(f"[Reranker] Upstage API 오류: {e} → 원래 순서 사용")
            reranked = chunks

        return reranked[:top_k]


class LLMReranker(Reranker):
    """
    LLM을 이용한 경량 재정렬
    API 비용이 추가되지만 Upstage Rerank가 없을 때 대안으로 사용
    상위 N개 후보에 대해 관련성 점수를 부여하여 재정렬합니다.
    """

    def __init__(self):
        from openai import OpenAI
        if config.UPSTAGE_API_KEY:
            self.client = OpenAI(
                api_key=config.UPSTAGE_API_KEY,
                base_url="https://api.upstage.ai/v1/solar",
            )
            self.model = "solar-mini"
        else:
            self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            self.model = "gpt-4o-mini"

    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = config.FINAL_TOP_K,
    ) -> List[Dict[str, Any]]:
        if len(chunks) <= top_k:
            return chunks[:top_k]

        # 각 청크에 점수 부여 (배치로 한 번에 처리)
        chunks_text = "\n\n".join([
            f"[청크 {i+1}] {c['text'][:500]}"
            for i, c in enumerate(chunks)
        ])

        prompt = f"""다음은 공정거래 의결서 검색 결과입니다. 질문과의 관련성을 기준으로 각 청크에 1-10점을 부여하세요.

질문: {query}

{chunks_text}

형식: 청크번호:점수 (예: 1:9, 2:3, 3:7, ...)
관련성 점수만 출력하세요."""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0,
            )
            score_text = resp.choices[0].message.content.strip()
            # 점수 파싱
            scores = {}
            for part in score_text.replace(" ", "").split(","):
                if ":" in part:
                    idx_str, score_str = part.split(":", 1)
                    try:
                        idx = int(idx_str) - 1
                        score = float(score_str)
                        if 0 <= idx < len(chunks):
                            scores[idx] = score
                    except ValueError:
                        pass

            # 점수 기준 정렬
            sorted_indices = sorted(
                range(len(chunks)),
                key=lambda i: scores.get(i, 0),
                reverse=True,
            )
            return [chunks[i] for i in sorted_indices[:top_k]]
        except Exception as e:
            print(f"[LLMReranker] 오류: {e} → 원래 순서 사용")
            return chunks[:top_k]


def get_reranker() -> Reranker:
    """설정에 따라 적절한 재정렬 모듈을 반환합니다."""
    mode = config.RERANKER.lower()
    if mode == "upstage":
        return UpstageReranker()
    elif mode == "llm":
        return LLMReranker()
    else:
        return NoReranker()
