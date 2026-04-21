"""
설정 관리 모듈
.env 파일 또는 환경변수에서 설정을 로드합니다.
"""
import os
from pathlib import Path

# .env 파일 로드 (있으면)
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

# 경로 설정
BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR.parent / "AI활용데이터"))
INDEX_DIR = Path(os.environ.get("INDEX_DIR", BASE_DIR / "index"))
CORPUS_PATH = INDEX_DIR / "corpus.json"
BM25_INDEX_PATH = INDEX_DIR / "bm25_index.pkl"
CHROMA_DIR = INDEX_DIR / "chroma_db"

INDEX_DIR.mkdir(parents=True, exist_ok=True)

# API 키
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY", "")

# 임베딩 설정
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "openai")
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
UPSTAGE_EMBEDDING_MODEL = "solar-embedding-1-large-query"

# 생성 모델 설정
GENERATION_MODEL = os.environ.get("GENERATION_MODEL", "gpt-4o-mini")

# 재정렬 설정
RERANKER = os.environ.get("RERANKER", "none")  # "upstage" or "none"

# 검색 설정
BM25_TOP_K = 20       # BM25 후보 수
DENSE_TOP_K = 20      # Dense 후보 수
FINAL_TOP_K = 5       # 최종 반환 청크 수
RRF_K = 60            # RRF 파라미터 (논문 권장값)

# 생성 설정
MAX_CONTEXT_CHUNKS = 5
MAX_TOKENS = 1024
TEMPERATURE = 0.1

# ChromaDB 컬렉션명
CHROMA_COLLECTION = "ftc_chunks"

# ── 오프라인/로컬 모드 ────────────────────────────────────────────────────
# 평가 환경(인터넷 차단)에서는 OFFLINE_MODE=true로 설정
OFFLINE_MODE = os.environ.get("OFFLINE_MODE", "false").lower() == "true"

# 로컬 LLM 설정 (OFFLINE_MODE=true 또는 USE_LOCAL_LLM=true 시 사용)
USE_LOCAL_LLM = os.environ.get("USE_LOCAL_LLM", "false").lower() == "true" or OFFLINE_MODE
LOCAL_MODEL_PATH = os.environ.get("LOCAL_MODEL_PATH", "/models/Qwen2.5-7B-Instruct")
LOCAL_MODEL_NAME = os.environ.get("LOCAL_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
LOCAL_MAX_NEW_TOKENS = int(os.environ.get("LOCAL_MAX_NEW_TOKENS", "512"))

# 로컬 임베딩 모델 설정 (OFFLINE_MODE=true 시 Dense 대신 사용)
USE_LOCAL_EMBED = os.environ.get("USE_LOCAL_EMBED", "false").lower() == "true" or OFFLINE_MODE
LOCAL_EMBED_PATH = os.environ.get("LOCAL_EMBED_PATH", "/models/bge-m3")
LOCAL_EMBED_NAME = os.environ.get("LOCAL_EMBED_NAME", "BAAI/bge-m3")
