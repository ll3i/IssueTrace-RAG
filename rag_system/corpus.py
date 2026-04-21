"""
코퍼스 로더
500개 의결서의 hybrid.json / metadata.json을 읽어 통합 코퍼스를 구성합니다.

corpus 구조:
    {
        chunk_id: {
            "text": str,
            "metadata": {
                "Header": str,
                "section": str,
                "chunk_type": str,    # text / table
                "chunk_index": int,
                "total_chunks": int,
                "chunk_id": str,
                # 문서 레벨 메타
                "doc_id": str,
                "doc_title": str,
                "violation_types": List[str],
                "action_types": List[str],
                "companies": List[str],
                "decision_date": str,
            }
        }
    }
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

sys.stdout.reconfigure(encoding="utf-8")

import config


def load_corpus(force_rebuild: bool = False) -> Dict[str, Dict[str, Any]]:
    """코퍼스를 로드합니다. 캐시가 있으면 캐시를 사용합니다."""
    if not force_rebuild and config.CORPUS_PATH.exists():
        print(f"[Corpus] 캐시 로드: {config.CORPUS_PATH}")
        with open(config.CORPUS_PATH, encoding="utf-8") as f:
            return json.load(f)

    print(f"[Corpus] {config.DATA_DIR} 에서 코퍼스 빌드 중...")
    corpus = _build_corpus(config.DATA_DIR)

    # 캐시 저장
    with open(config.CORPUS_PATH, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False)
    print(f"[Corpus] {len(corpus)}개 청크 저장 완료: {config.CORPUS_PATH}")
    return corpus


def _build_corpus(data_dir: Path) -> Dict[str, Dict[str, Any]]:
    """모든 hybrid.json을 읽어 corpus 딕셔너리를 구성합니다."""
    corpus: Dict[str, Dict[str, Any]] = {}
    hybrid_files = sorted([
        f for f in os.listdir(data_dir) if f.endswith("_hybrid.json")
    ])

    for fname in hybrid_files:
        base = fname[: -len("_hybrid.json")]
        hybrid_path = data_dir / fname
        meta_path = data_dir / f"{base}_metadata.json"

        # 문서 메타 로드
        doc_meta = _load_doc_meta(meta_path)

        # 청크 로드
        with open(hybrid_path, encoding="utf-8") as f:
            chunks = json.load(f)

        for chunk in chunks:
            chunk_id = chunk["metadata"]["chunk_id"]
            text = chunk["page_content"]

            # 청크 레벨 메타 + 문서 레벨 메타 병합
            chunk_meta = {**chunk["metadata"], **doc_meta}
            corpus[chunk_id] = {"text": text, "metadata": chunk_meta}

    return corpus


def _load_doc_meta(meta_path: Path) -> Dict[str, Any]:
    """metadata.json에서 문서 레벨 정보를 추출합니다."""
    if not meta_path.exists():
        return {}

    with open(meta_path, encoding="utf-8") as f:
        raw = json.load(f)

    피심인정보 = raw.get("피심인정보", [])
    return {
        "doc_id": raw.get("의결서파일명", ""),
        "doc_title": raw.get("의결서제목", ""),
        "decision_date": raw.get("공개일자", ""),
        "violation_types": list({p.get("위반유형", "") for p in 피심인정보 if p.get("위반유형")}),
        "sub_violation_types": list({p.get("세부위반유형", "") for p in 피심인정보 if p.get("세부위반유형")}),
        "action_types": list({p.get("조치유형", "") for p in 피심인정보 if p.get("조치유형")}),
        "companies": list({p.get("피심인기업명", "") for p in 피심인정보 if p.get("피심인기업명")}),
    }


def get_chunk_ids(corpus: Dict[str, Dict[str, Any]]) -> list:
    return list(corpus.keys())


def get_texts(corpus: Dict[str, Dict[str, Any]]) -> list:
    return [v["text"] for v in corpus.values()]


if __name__ == "__main__":
    corpus = load_corpus(force_rebuild=True)
    print(f"총 {len(corpus)}개 청크")
    sample_id = next(iter(corpus))
    print(f"샘플 chunk_id: {sample_id}")
    print(f"샘플 메타: {corpus[sample_id]['metadata']}")
    print(f"샘플 텍스트 (100자): {corpus[sample_id]['text'][:100]}")
