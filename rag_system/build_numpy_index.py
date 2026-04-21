"""
Numpy 기반 벡터 인덱스 빌더
ChromaDB 대신 .npy 파일로 임베딩을 저장합니다.
중단 후 재시작 가능한 체크포인트 방식입니다.

출력 파일:
  index/embeddings.npy    - float16, shape=(N, 4096)
  index/embed_ids.json    - chunk_id 목록
"""
import sys, time, json, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import numpy as np
from openai import OpenAI
import config
from corpus import load_corpus

BATCH = 50
MODEL = "solar-embedding-1-large-passage"
IDS_PATH   = config.INDEX_DIR / "embed_ids.json"
EMBED_PATH = config.INDEX_DIR / "embeddings.npy"
CKPT_PATH  = config.INDEX_DIR / "numpy_checkpoint.json"

def load_checkpoint():
    if CKPT_PATH.exists():
        with open(CKPT_PATH) as f:
            return json.load(f)
    return {"done": 0}

def save_checkpoint(done):
    with open(CKPT_PATH, "w") as f:
        json.dump({"done": done}, f)

def clean_text(text):
    text = text.strip()
    return text[:8000] if text else "내용 없음"

def embed_batch(client, texts):
    """배치 임베딩, 실패 시 단건 재시도"""
    try:
        resp = client.embeddings.create(model=MODEL, input=texts)
        return [item.embedding for item in resp.data]
    except Exception as e:
        print(f"  [배치 오류] {e[:80]} → 단건 재시도")
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
    start = ckpt["done"]
    print(f"체크포인트: {start}번부터 재시작")

    # 기존 임베딩 로드 (있으면)
    if start > 0 and EMBED_PATH.exists():
        existing = np.load(str(EMBED_PATH))
        all_embeddings = list(existing.astype(np.float32))
        print(f"기존 임베딩 로드: {len(all_embeddings)}개")
    else:
        all_embeddings = []
        start = 0

    # Upstage 클라이언트
    client = OpenAI(
        api_key=config.UPSTAGE_API_KEY,
        base_url="https://api.upstage.ai/v1",
    )

    t0 = time.time()
    SAVE_EVERY = 500  # 500개마다 중간 저장

    for i in range(start, total, BATCH):
        batch_ids_texts = list(zip(all_ids[i:i+BATCH], all_texts[i:i+BATCH]))
        batch_texts = [clean_text(t) for _, t in batch_ids_texts]

        embeddings = embed_batch(client, batch_texts)
        all_embeddings.extend(embeddings)

        done = len(all_embeddings)
        elapsed = time.time() - t0
        eta = elapsed / max(1, done - start) * max(0, total - done)
        print(f"  [{done}/{total}] {elapsed:.0f}s, ETA {eta:.0f}s")

        # 중간 저장
        if done % SAVE_EVERY < BATCH or done >= total:
            arr = np.array(all_embeddings, dtype=np.float16)
            np.save(str(EMBED_PATH), arr)
            with open(IDS_PATH, "w", encoding="utf-8") as f:
                json.dump(all_ids[:done], f, ensure_ascii=False)
            save_checkpoint(done)
            print(f"  → 저장 완료 ({done}개)")

    # 최종 저장
    arr = np.array(all_embeddings, dtype=np.float16)
    np.save(str(EMBED_PATH), arr)
    with open(IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_ids[:len(all_embeddings)], f, ensure_ascii=False)
    save_checkpoint(len(all_embeddings))

    print(f"\n완료! shape={arr.shape}, 파일={EMBED_PATH} ({os.path.getsize(EMBED_PATH)//1024//1024}MB)")
    print(f"총 {time.time()-t0:.0f}s 소요")

if __name__ == "__main__":
    main()
