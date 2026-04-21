"""
인덱스 빌드 스크립트
최초 1회 실행 후 저장된 인덱스를 재사용합니다.

실행:
    python build_index.py           # BM25 + Dense 모두 빌드
    python build_index.py --bm25    # BM25만 빌드
    python build_index.py --dense   # Dense만 빌드
    python build_index.py --force   # 강제 재빌드
"""
import argparse
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import config
from corpus import load_corpus
from bm25_retriever import BM25Retriever
from dense_retriever import DenseRetriever


def build_bm25(corpus: dict, force: bool = False) -> None:
    if not force and config.BM25_INDEX_PATH.exists():
        print(f"[BM25] 이미 존재합니다: {config.BM25_INDEX_PATH}")
        print("  강제 재빌드: --force 옵션 사용")
        return

    t0 = time.time()
    retriever = BM25Retriever()
    retriever.build(corpus)
    retriever.save()
    print(f"[BM25] 완료 ({time.time() - t0:.1f}s)")


def build_dense(corpus: dict, force: bool = False) -> None:
    dense = DenseRetriever()

    if not force and dense.is_built():
        print(f"[Dense] 이미 존재합니다: {config.CHROMA_DIR}")
        print("  강제 재빌드: --force 옵션 사용")
        return

    # API 키 확인
    if config.EMBEDDING_PROVIDER == "upstage" and not config.UPSTAGE_API_KEY:
        print("[Dense] 오류: UPSTAGE_API_KEY가 설정되지 않았습니다.")
        print("  .env 파일에 UPSTAGE_API_KEY를 설정하거나")
        print("  EMBEDDING_PROVIDER=openai로 변경하세요.")
        return

    if config.EMBEDDING_PROVIDER == "openai" and not config.OPENAI_API_KEY:
        print("[Dense] 오류: OPENAI_API_KEY가 설정되지 않았습니다.")
        print("  .env 파일에 OPENAI_API_KEY를 설정하세요.")
        return

    t0 = time.time()
    dense.build(corpus)
    elapsed = time.time() - t0
    print(f"[Dense] 완료 ({elapsed:.1f}s)")
    print(f"  예상 API 비용 (OpenAI text-embedding-3-small):")
    total_tokens = sum(len(v["text"].split()) * 1.3 for v in corpus.values())
    cost = total_tokens / 1_000_000 * 0.02  # $0.02 per 1M tokens
    print(f"  약 {total_tokens/1000:.0f}K 토큰 → $~{cost:.2f}")


def main():
    parser = argparse.ArgumentParser(description="공정거래 RAG 인덱스 빌더")
    parser.add_argument("--bm25", action="store_true", help="BM25만 빌드")
    parser.add_argument("--dense", action="store_true", help="Dense만 빌드")
    parser.add_argument("--force", action="store_true", help="강제 재빌드")
    args = parser.parse_args()

    build_all = not args.bm25 and not args.dense

    print("=" * 60)
    print("IssueTrace RAG - 인덱스 빌더")
    print("=" * 60)
    print(f"데이터 경로: {config.DATA_DIR}")
    print(f"인덱스 경로: {config.INDEX_DIR}")
    print(f"임베딩 제공자: {config.EMBEDDING_PROVIDER}")
    print()

    # 코퍼스 로드
    t0 = time.time()
    corpus = load_corpus(force_rebuild=args.force)
    print(f"코퍼스 로드: {len(corpus)}개 청크 ({time.time() - t0:.1f}s)")
    print()

    # BM25 빌드
    if build_all or args.bm25:
        build_bm25(corpus, force=args.force)
        print()

    # Dense 빌드
    if build_all or args.dense:
        build_dense(corpus, force=args.force)
        print()

    print("=" * 60)
    print("인덱스 빌드 완료! 이제 server.py를 실행하세요.")
    print()
    print("서버 시작:")
    print("  python server.py")
    print()
    print("CLI 테스트:")
    print("  python pipeline.py \"담합 행위에 대한 과징금 사례는?\"")


if __name__ == "__main__":
    main()
