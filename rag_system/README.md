# IssueTrace RAG — 공정거래 의결서 AI 질의응답 시스템

제2회 공정위 AI·데이터 활용 공모전 **Track 2 (AI 모델 개발)** 제출용 RAG 시스템

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [평가 기준](#2-평가-기준)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [디렉토리 구조](#4-디렉토리-구조)
5. [파일별 설명](#5-파일별-설명)
6. [인덱스 구축 과정](#6-인덱스-구축-과정)
7. [로컬 개발 환경 실행](#7-로컬-개발-환경-실행)
8. [Docker 제출 이미지 빌드](#8-docker-제출-이미지-빌드)
9. [API 규격](#9-api-규격)
10. [주요 설계 결정 및 트러블슈팅](#10-주요-설계-결정-및-트러블슈팅)
11. [환경변수 설정](#11-환경변수-설정)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 데이터 | 공정거래위원회 의결서 500개 |
| 청크 수 | 31,879개 |
| 검색 방식 | Hybrid RAG (BM25 + Solar Dense + RRF) |
| 생성 모델 | 개발: Solar-Pro API / 평가: Qwen2.5-7B-Instruct (로컬) |
| 임베딩 모델 | 개발: solar-embedding-1-large (Upstage) / 평가: BM25 단독 |
| 응답 시간 | 30초 이내 (A100 기준 약 10~20초) |

---

## 2. 평가 기준

```
Final Score = 0.35 × Recall@5
            + 0.15 × MRR
            + 0.30 × BERTScore
            + 0.20 × F1
```

| 지표 | 범주 | 가중치 | 설명 |
|------|------|--------|------|
| Recall@5 | Retrieval | 35% | Top-5 청크 중 정답 포함 여부 |
| MRR | Retrieval | 15% | 정답 청크 순위 역수 평균 |
| BERTScore | Generation | 30% | 의미적 유사도 |
| F1 | Generation | 20% | 토큰 수준 겹침 |

> **핵심**: Retrieval 성능이 나빠지면 Generation 점수도 함께 하락하므로 검색 품질이 최우선

---

## 3. 시스템 아키텍처

```
질문 입력
   │
   ▼
[쿼리 확장] expand_query()
   │  공정거래 도메인 키워드 사전 기반 규칙 확장
   │  예: "담합" → "부당한 공동행위", "가격 담합", "입찰 담합" 추가
   │
   ▼
[Hybrid Retrieval] HybridRetriever
   ├─ BM25Retriever   : 키워드 희소 검색 (top-20)
   │    └─ 토크나이저: 공백 분리 + 한국어 문자 2-gram
   └─ DenseRetriever  : Solar 임베딩 의미 검색 (top-20)
        └─ 색인: solar-embedding-1-large-passage (4096dim, float16)
        └─ 검색: solar-embedding-1-large-query
        └─ 저장: embeddings.npy (numpy, 249MB)
   │
   ▼
[RRF 결합] Reciprocal Rank Fusion (k=60)
   │  score = Σ 1/(k + rank)
   │
   ▼
[Reranker] (현재 none, 추후 활성화 가능)
   │
   ▼
[Top-5 선정] _ensure_five()
   │  5개 미만 시 추가 후보에서 채움
   │
   ▼
[답변 생성] generate_answer()
   ├─ 개발 환경: Solar-Pro API (Upstage)
   └─ 평가 환경: Qwen2.5-7B-Instruct (로컬, transformers)
   │
   ▼
반환: retrieved_chunk_ids (5개) + answer
```

### 오프라인 모드 (평가 환경)

평가 환경은 인터넷 완전 차단. `OFFLINE_MODE=true` 설정 시:
- Dense Retriever 스킵 → **BM25 단독 검색**
- Solar API 대신 **로컬 Qwen2.5-7B-Instruct** 사용
- 모델은 서버 시작 시 `lifespan`에서 **사전 로드** (첫 요청 30초 초과 방지)

---

## 4. 디렉토리 구조

```
rag_system/
├── server.py              # FastAPI 서버 (메인 진입점)
├── pipeline.py            # RAG 파이프라인 통합
├── config.py              # 환경변수 및 설정 관리
├── corpus.py              # 의결서 데이터 로드
├── bm25_retriever.py      # BM25 희소 검색
├── dense_retriever.py     # Solar 임베딩 밀집 검색 (numpy)
├── hybrid_retriever.py    # BM25 + Dense RRF 결합
├── reranker.py            # 재정렬 (현재 none)
├── generator.py           # 답변 생성 (API/로컬 분기)
├── generator_local.py     # 로컬 LLM 생성 (Qwen2.5-7B)
├── build_numpy_index.py   # Dense 인덱스 빌드 스크립트
├── download_models.py     # 로컬 모델 사전 다운로드 스크립트
├── entrypoint.sh          # Docker entrypoint (경로 변환 버그 우회)
├── Dockerfile             # 제출용 Docker 이미지
├── .dockerignore
├── requirements.txt
├── .env                   # API 키 (git 제외)
├── static/
│   └── index.html         # 대시보드 UI
├── index/                 # 빌드된 인덱스 파일들
│   ├── corpus.json        # 31,879개 청크 (chunk_id → {text, metadata})
│   ├── bm25_index.pkl     # BM25 직렬화 인덱스
│   ├── embeddings.npy     # Dense 임베딩 (float16, shape=31879×4096, 249MB)
│   └── embed_ids.json     # 임베딩 순서 대응 chunk_id 목록
└── models/
    └── Qwen2.5-7B-Instruct/   # 로컬 LLM (15GB, git 제외)
```

---

## 5. 파일별 설명

### `server.py`
FastAPI 서버. 두 가지 엔드포인트 제공:

| 엔드포인트 | 용도 |
|-----------|------|
| `GET /health` | 평가 서버 헬스체크 |
| `POST /predict` | **평가 서버 주요 엔드포인트** |
| `POST /query` | 대시보드 UI용 (retrieved_chunks 포함 확장 응답) |
| `GET /stats` | 코퍼스 통계 |
| `GET /` | 대시보드 UI 서빙 |

서버 시작 시 `lifespan`에서:
1. RAG 파이프라인 초기화 (코퍼스 로드, BM25/Dense 인덱스 로드)
2. `USE_LOCAL_LLM=true` 시 Qwen 모델 사전 로드 (`preload()`)

### `pipeline.py`
```
RAGPipeline.run(question) → RAGResult
  1. expand_query()     쿼리 확장
  2. hybrid.get_chunks_with_text()   후보 검색
  3. reranker.rerank()  재정렬
  4. _ensure_five()     5개 보장
  5. generate_answer()  답변 생성
```

`OFFLINE_MODE=true` 시 Dense 로드를 스킵하고 `_BM25OnlyRetriever`를 사용.

### `bm25_retriever.py`
- 한국어 토크나이저: **공백 분리 + 문자 2-gram 혼합** (konlpy 의존성 없음)
- `rank_bm25.BM25Okapi` 사용
- 인덱스를 `bm25_index.pkl`로 직렬화/역직렬화

### `dense_retriever.py`
- ChromaDB 대신 **Numpy .npy 파일** 사용 (ChromaDB HNSW 인덱스 손상 문제로 교체)
- 색인 시: `solar-embedding-1-large-passage` (4096dim)
- 검색 시: `solar-embedding-1-large-query` (비대칭 임베딩)
- L2 정규화 후 행렬 내적으로 코사인 유사도 계산

### `generator.py` / `generator_local.py`
- `config.USE_LOCAL_LLM` 플래그로 분기
- 로컬 모드: `transformers.AutoModelForCausalLM` + `device_map="auto"` + `torch.float16`
- Greedy decoding 권장 (`temperature=0.1`)

### `hybrid_retriever.py`
RRF 점수 계산:
```python
score = sum(1 / (k + rank) for k in [bm25_rank, dense_rank])
```

### `entrypoint.sh`
```bash
#!/bin/bash
export LOCAL_MODEL_PATH=/models/Qwen2.5-7B-Instruct
export OFFLINE_MODE=true
...
exec "$@"
```
**목적**: Windows Git Bash의 MSYS 경로 변환 버그 우회.  
Dockerfile `ENV`에 `/models/...` 경로를 설정하면 Git Bash가 `C:/Program Files/Git/models/...`로 변환하는 문제가 있어, 컨테이너 내부 bash 스크립트에서 직접 설정.

---

## 6. 인덱스 구축 과정

### BM25 인덱스 빌드
```bash
python build_index.py
# index/corpus.json + index/bm25_index.pkl 생성
```

### Dense (Numpy) 임베딩 인덱스 빌드
```bash
python build_numpy_index.py
# index/embeddings.npy (float16, 31879×4096, 249MB)
# index/embed_ids.json 생성
# 체크포인트 방식으로 중단 후 재시작 가능
# 약 500개 단위로 저장
```

> Upstage API 비용 발생. 빌드 완료 후에는 재실행 불필요.

---

## 7. 로컬 개발 환경 실행

### 환경 설정
```bash
cd rag_system

# Python 3.11
pip install -r requirements.txt

# .env 파일
cat > .env << EOF
UPSTAGE_API_KEY=<your_key>
EMBEDDING_PROVIDER=upstage
GENERATION_MODEL=solar-pro
RERANKER=none
DATA_DIR=c:/Users/SSAFY/Desktop/공정거래_데이터/AI활용데이터
INDEX_DIR=c:/Users/SSAFY/Desktop/공정거래_데이터/rag_system/index
EOF
```

### 서버 실행
```bash
python server.py
# 또는
uvicorn server:app --host 0.0.0.0 --port 8001
```

### 대시보드 접속
```
http://localhost:8001
```

### CLI 테스트
```bash
python pipeline.py "BGF리테일의 판매촉진비용 위반 행위는 무엇인가요?"
```

---

## 8. Docker 제출 이미지 빌드

### 사전 준비: 로컬 모델 다운로드
```bash
# 인터넷이 되는 환경에서 실행
python download_models.py
# models/Qwen2.5-7B-Instruct/ (15GB) 생성
```

### Docker 이미지 빌드
```bash
docker build -t rag-submission:latest .
# 약 30~60분 소요 (15GB 모델 복사 포함)
# 최종 이미지 크기: ~36.7GB
```

### 로컬 테스트 (오프라인 모드)
```bash
docker run --gpus all -p 8000:8000 --name rag-test rag-submission:latest

# 헬스체크
curl http://localhost:8000/health

# 예측 테스트
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"id": "eval_0001", "question": "BGF리테일 판매촉진비용 위반"}'
```

### 제출용 tar 생성
```bash
docker save rag-submission:latest -o submission.tar
# 약 14GB
```

### 제출
제출 포털에 `submission.tar` 업로드.

---

## 9. API 규격

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /predict` — 평가 서버용
**Request:**
```json
{
  "id": "eval_0001",
  "question": "BGF리테일의 판매촉진비용 위반 행위는 무엇인가요?"
}
```

**Response:**
```json
{
  "id": "eval_0001",
  "retrieved_chunk_ids": [
    "DOC-4cf52958-dd7f-4424-b65e-420d0d8c02d7-CH-001",
    "DOC-4cf52958-dd7f-4424-b65e-420d0d8c02d7-CH-052",
    "DOC-4cf52958-dd7f-4424-b65e-420d0d8c02d7-CH-053",
    "DOC-4cf52958-dd7f-4424-b65e-420d0d8c02d7-CH-066",
    "DOC-2b7dd00f-3936-4b9b-b36a-bb0a8e242a02-CH-029"
  ],
  "answer": "BGF리테일은 판매촉진비용을 50% 초과하여 납품업자에게 전가하는 행위를 하였으며..."
}
```

**필수 규칙:**
- `retrieved_chunk_ids`: 정확히 5개, 중복 없음, 코퍼스에 존재하는 ID만
- 배열 순서 = 검색 순위 (1위가 가장 관련성 높음)
- 응답 시간 30초 이내

### `POST /query` — 대시보드용 (추가 필드 포함)
```json
{
  "question": "질문",
  "chunk_ids": ["..."],
  "answer": "...",
  "elapsed_sec": 4.23,
  "retrieved_chunks": [
    { "chunk_id": "...", "text": "...", "metadata": {...} }
  ]
}
```

---

## 10. 주요 설계 결정 및 트러블슈팅

### ChromaDB → Numpy 전환
**문제**: ChromaDB 1.5.5에서 HNSW 인덱스가 비동기 Rust 컴팩터에 의해 영구 저장되지 않는 버그.  
임베딩을 빌드해도 다음 실행 시 인덱스가 비어있는 현상 발생.

**해결**: ChromaDB를 완전 제거하고 `numpy .npy` 파일로 직접 저장.
- `embeddings.npy`: float16, shape=(31879, 4096), 249MB
- `embed_ids.json`: chunk_id 목록
- 로드 후 float32로 변환 + L2 정규화 → 행렬 내적으로 코사인 유사도 계산

### Upstage API 비대칭 임베딩
- 색인(문서): `solar-embedding-1-large-passage`
- 검색(쿼리): `solar-embedding-1-large-query`
- ChromaDB는 단일 임베딩 함수만 지원 → Numpy 방식이 비대칭 임베딩에 더 적합

### Upstage Rerank API 미지원
`POST /v1/rerank` 엔드포인트가 404 반환 → `RERANKER=none`으로 설정. RRF가 재정렬 역할 대체.

### 오프라인 평가 환경 대응
평가 환경은 인터넷 완전 차단이므로 Upstage Solar API 사용 불가.

| 컴포넌트 | 개발 환경 | 평가 환경 |
|---------|----------|----------|
| 검색 | BM25 + Solar Dense | BM25 단독 (`OFFLINE_MODE=true`) |
| 임베딩 | solar-embedding-1-large-query | — (BM25만 사용) |
| 생성 | Solar-Pro API | Qwen2.5-7B-Instruct (로컬) |

### Git Bash MSYS 경로 변환 버그
**문제**: Docker `ENV LOCAL_MODEL_PATH=/models/Qwen2.5-7B-Instruct` 설정이  
Windows Git Bash에서 `C:/Program Files/Git/models/Qwen2.5-7B-Instruct`로 자동 변환됨.

**해결**: `entrypoint.sh`에서 컨테이너 내부 bash로 환경변수를 직접 설정:
```bash
#!/bin/bash
export LOCAL_MODEL_PATH=/models/Qwen2.5-7B-Instruct
exec "$@"
```

### 첫 요청 30초 초과 문제
Qwen 모델 로드 시간이 GPU 기준 약 1~2분 소요. 평가 서버의 첫 질문이 30초를 초과하면 해당 문항 전체 0점 처리.

**해결**: `server.py` `lifespan`에서 서버 시작 시 모델 사전 로드:
```python
if config.USE_LOCAL_LLM:
    from generator_local import preload
    await asyncio.get_event_loop().run_in_executor(None, preload)
```

HEALTHCHECK `start-period=180s`로 모델 로드 완료 후 헬스체크 시작.

### 한국어 BM25 토크나이저 (konlpy 없이)
mecab, konlpy 등 형태소 분석기 없이도 효과적인 한국어 검색을 위해:
- 공백 분리 토큰 + 문자 2-gram 조합
- 법률 문서는 어절 단위 검색으로도 충분한 성능

---

## 11. 환경변수 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `UPSTAGE_API_KEY` | — | Upstage API 키 (개발 환경) |
| `EMBEDDING_PROVIDER` | `upstage` | 임베딩 제공자 |
| `GENERATION_MODEL` | `solar-pro` | 생성 모델 (개발 환경) |
| `RERANKER` | `none` | 재정렬기 |
| `OFFLINE_MODE` | `false` | `true` 시 BM25 단독 + 로컬 LLM |
| `USE_LOCAL_LLM` | `false` | `true` 시 로컬 LLM 사용 |
| `LOCAL_MODEL_PATH` | `/models/Qwen2.5-7B-Instruct` | 로컬 LLM 경로 |
| `LOCAL_MAX_NEW_TOKENS` | `512` | 로컬 LLM 최대 생성 토큰 |
| `INDEX_DIR` | `./index` | 인덱스 파일 디렉토리 |
| `DATA_DIR` | `../AI활용데이터` | 원본 의결서 JSON 디렉토리 |
| `PORT` | `8001` | 서버 포트 |

### 개발 환경 `.env`
```env
UPSTAGE_API_KEY=up_xxxxxxxxxxxxxxxx
EMBEDDING_PROVIDER=upstage
GENERATION_MODEL=solar-pro
RERANKER=none
DATA_DIR=c:/Users/SSAFY/Desktop/공정거래_데이터/AI활용데이터
INDEX_DIR=c:/Users/SSAFY/Desktop/공정거래_데이터/rag_system/index
```

### 평가 환경 (Dockerfile에서 entrypoint.sh로 고정)
```env
OFFLINE_MODE=true
USE_LOCAL_LLM=true
LOCAL_MODEL_PATH=/models/Qwen2.5-7B-Instruct
INDEX_DIR=/app/index
PORT=8000
```

---

## 제출 파일

```
submission.tar   # 14.1GB — docker load 후 즉시 실행 가능
```

```bash
# 평가 서버에서 실행
docker load -i submission.tar
docker run --gpus all -p 8000:8000 rag-submission:latest
```
