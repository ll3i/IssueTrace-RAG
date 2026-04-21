# ──────────────────────────────────────────────────────────────────────────
#  IssueTrace RAG — 공모전 제출용 Dockerfile (완전 오프라인)
#  평가 환경: A100 80G × 2, 인터넷 완전 차단 (offline)
#  엔드포인트: GET /health  POST /predict
#  포함 모델: Qwen2.5-7B-Instruct (로컬 번들)
# ──────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# 헬스체크용 curl
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# pip 업그레이드
RUN pip install --no-cache-dir --upgrade pip

# PyTorch (CUDA 12.1) — 가장 먼저 설치해 레이어 캐시 활용
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cu121

# 나머지 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드
COPY *.py ./
COPY static/ ./static/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 인덱스 (BM25 pkl, corpus.json, embeddings.npy, embed_ids.json)
COPY index/ ./index/

# LLM 모델 번들 (완전 오프라인 평가 환경용)
COPY models/ /models/

EXPOSE 8000

# 헬스체크 (모델 로드 시간 고려해 start-period=180s)
HEALTHCHECK --interval=30s --timeout=15s --start-period=180s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# entrypoint.sh 가 경로를 고정 설정 → Git Bash MSYS 변환 우회
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "server.py"]
