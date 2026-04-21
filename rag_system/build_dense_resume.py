"""
Dense 인덱스 이어서 빌드 (체크포인트 재시작)
이미 ChromaDB에 저장된 chunk_id는 건너뜁니다.
"""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import chromadb
from chromadb.config import Settings
import config
from corpus import load_corpus
from dense_retriever import embed_passages, _clean_text

data_dir = config.DATA_DIR
index_dir = config.INDEX_DIR

# 코퍼스 로드
corpus = load_corpus()
all_ids = list(corpus.keys())
all_texts = [corpus[cid]['text'] for cid in all_ids]
print(f"전체 청크: {len(all_ids)}개")

# ChromaDB 열기
client = chromadb.PersistentClient(
    path=str(config.CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False),
)

try:
    collection = client.get_collection(config.CHROMA_COLLECTION)
    existing_count = collection.count()
    print(f"기존 저장된 청크: {existing_count}개")
except Exception:
    collection = client.create_collection(
        name=config.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    existing_count = 0
    print("새 컬렉션 생성")

# 이미 저장된 ID 확인 (최대 10만개씩 가져오기)
if existing_count > 0:
    existing_result = collection.get(limit=existing_count, include=[])
    existing_ids = set(existing_result['ids'])
    print(f"기존 ID 수: {len(existing_ids)}개")
else:
    existing_ids = set()

# 아직 저장되지 않은 청크 필터
remaining = [(cid, text) for cid, text in zip(all_ids, all_texts) if cid not in existing_ids]
print(f"남은 청크: {len(remaining)}개")

if not remaining:
    print("모든 청크가 이미 저장되었습니다!")
    sys.exit(0)

# 배치 임베딩 및 저장
BATCH = 50
total = len(remaining)
t0 = time.time()

for i in range(0, total, BATCH):
    batch_items = remaining[i : i + BATCH]
    batch_ids = [item[0] for item in batch_items]
    batch_texts = [_clean_text(item[1]) for item in batch_items]

    try:
        embeddings = embed_passages(batch_texts)
        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            embeddings=embeddings,
        )
    except Exception as e:
        print(f"  [배치 오류 {i}~{i+BATCH}] {e} → 단건 처리")
        from openai import OpenAI
        client_emb = OpenAI(
            api_key=config.UPSTAGE_API_KEY,
            base_url="https://api.upstage.ai/v1",
        )
        for cid, text in batch_items:
            try:
                resp = client_emb.embeddings.create(
                    model="solar-embedding-1-large-passage",
                    input=_clean_text(text),
                )
                collection.add(
                    ids=[cid],
                    documents=[text[:8000]],
                    embeddings=[resp.data[0].embedding],
                )
            except Exception as e2:
                print(f"    [단건 오류] {cid}: {e2} → 건너뜀")

    done = min(i + BATCH, total)
    elapsed = time.time() - t0
    if done > 0:
        eta = elapsed / done * (total - done)
        print(f"  [{done}/{total}] {elapsed:.0f}s 경과, ETA {eta:.0f}s, 총저장={collection.count()}")

print(f"\n완료! 총 {collection.count()}개 저장 ({time.time()-t0:.0f}s)")
