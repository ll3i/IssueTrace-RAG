"""
Dense 인덱스 빌드 - 체크포인트 방식
배치 단위로 진행 상황을 저장하여 중단 후 재시작이 가능합니다.
"""
import sys, time, json, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import chromadb
from chromadb.config import Settings
from openai import OpenAI
import config
from corpus import load_corpus

BATCH = 50
CHECKPOINT_FILE = str(config.INDEX_DIR / "dense_checkpoint.json")
MODEL = "solar-embedding-1-large-passage"

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"done_ids": [], "last_idx": 0}

def save_checkpoint(done_ids, last_idx):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"done_ids": done_ids, "last_idx": last_idx}, f)

def clean_text(text: str) -> str:
    text = text.strip()
    return text[:8000] if text else "내용 없음"

def embed_batch(client, texts):
    """배치 임베딩, 실패 시 단건 재시도"""
    try:
        resp = client.embeddings.create(model=MODEL, input=texts)
        return [item.embedding for item in resp.data]
    except Exception as e:
        print(f"  [배치 오류] {e} → 단건 재시도")
        results = []
        for text in texts:
            try:
                resp = client.embeddings.create(model=MODEL, input=text)
                results.append(resp.data[0].embedding)
            except Exception as e2:
                print(f"  [단건 오류] {e2} → 영벡터")
                results.append([0.0] * 4096)
        return results

def main():
    corpus = load_corpus()
    all_ids = list(corpus.keys())
    all_texts = [corpus[cid]['text'] for cid in all_ids]
    total = len(all_ids)
    print(f"전체 청크: {total}개")

    # 체크포인트 로드
    ckpt = load_checkpoint()
    done_set = set(ckpt["done_ids"])
    start_idx = ckpt["last_idx"]
    print(f"체크포인트: {len(done_set)}개 완료, {start_idx}번부터 재시작")

    # ChromaDB 초기화
    chroma = chromadb.PersistentClient(
        path=str(config.CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    try:
        collection = chroma.get_collection(config.CHROMA_COLLECTION)
        print(f"기존 컬렉션 로드: {collection.count()}개")
    except Exception:
        collection = chroma.create_collection(
            name=config.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        print("새 컬렉션 생성")

    # Upstage 클라이언트
    upstage = OpenAI(
        api_key=config.UPSTAGE_API_KEY,
        base_url="https://api.upstage.ai/v1",
    )

    # 남은 청크 필터 (done_set 제외)
    remaining = [
        (i, cid, all_texts[i])
        for i, cid in enumerate(all_ids)
        if cid not in done_set
    ]
    print(f"남은 청크: {len(remaining)}개")

    if not remaining:
        print("모두 완료!")
        return

    t0 = time.time()
    new_done = []

    for batch_start in range(0, len(remaining), BATCH):
        batch = remaining[batch_start : batch_start + BATCH]
        batch_ids = [item[1] for item in batch]
        batch_texts = [clean_text(item[2]) for item in batch]

        embeddings = embed_batch(upstage, batch_texts)

        # ChromaDB에 저장
        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            embeddings=embeddings,
        )

        new_done.extend(batch_ids)
        done_count = len(done_set) + len(new_done)
        elapsed = time.time() - t0
        rem = len(remaining) - (batch_start + BATCH)
        eta = elapsed / max(1, batch_start + BATCH) * max(0, rem)

        print(f"  [{done_count}/{total}] {elapsed:.0f}s, ETA {eta:.0f}s")

        # 매 20배치마다 체크포인트 저장
        if len(new_done) % (BATCH * 20) == 0:
            save_checkpoint(list(done_set) + new_done, batch_start)

    # 최종 체크포인트 저장
    save_checkpoint(list(done_set) + new_done, len(remaining))
    print(f"\n완료! 총 {collection.count()}개 저장 ({time.time()-t0:.0f}s)")

if __name__ == "__main__":
    main()
