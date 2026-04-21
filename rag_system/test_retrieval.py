"""
BM25 검색 기능 단독 테스트 (API 키 불필요)
Dense 임베딩 없이 BM25 검색의 정확도를 확인합니다.
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from corpus import load_corpus
from bm25_retriever import BM25Retriever
from hybrid_retriever import reciprocal_rank_fusion
import config

# ── 샘플 질문 ─────────────────────────────────────────────────────────────

TEST_QUERIES = [
    "BGF리테일의 판매촉진비용 위반 행위는 무엇인가요?",
    "담합 행위로 인한 과징금 부과 사례를 알려주세요",
    "시장지배적 지위남용 행위에 대한 시정명령 내용은?",
    "하도급법 위반 행위와 제재 조치는?",
    "전자상거래 소비자보호법 위반 사례는?",
]


def main():
    print("=" * 60)
    print("IssueTrace RAG - BM25 검색 테스트")
    print("=" * 60)

    # 코퍼스 로드
    t0 = time.time()
    corpus = load_corpus()
    print(f"코퍼스 로드: {len(corpus)}개 청크 ({time.time()-t0:.1f}s)\n")

    # BM25 로드
    t0 = time.time()
    bm25 = BM25Retriever()
    bm25.load()
    print(f"BM25 로드: {time.time()-t0:.1f}s\n")

    # 각 쿼리 테스트
    for query in TEST_QUERIES:
        t0 = time.time()
        results = bm25.search(query, top_k=config.FINAL_TOP_K)
        elapsed = time.time() - t0

        print(f"Q: {query}")
        print(f"   검색 시간: {elapsed*1000:.1f}ms")
        for rank, (cid, score) in enumerate(results, 1):
            meta = corpus[cid]["metadata"]
            title = meta.get("doc_title", "")[:50]
            section = meta.get("section", "")
            chunk_type = meta.get("chunk_type", "")
            print(f"   {rank}. [{score:.1f}] {title}")
            print(f"      chunk_id: {cid}")
            print(f"      section: {section} | type: {chunk_type}")
            text_preview = corpus[cid]["text"][:100].replace("\n", " ")
            print(f"      텍스트: {text_preview}...")
        print()

    print("=" * 60)
    print("테스트 완료!")
    print()
    print("다음 단계:")
    print("  1. .env 파일에 API 키 설정")
    print("  2. python build_index.py --dense  (Dense 인덱스 빌드)")
    print("  3. python server.py               (서버 시작)")


if __name__ == "__main__":
    main()
