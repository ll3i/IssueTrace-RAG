#!/bin/bash
# Git Bash MSYS 경로 변환 우회 — 컨테이너 내부에서 경로를 직접 설정
export LOCAL_MODEL_PATH=/models/Qwen2.5-7B-Instruct
export OFFLINE_MODE=true
export USE_LOCAL_LLM=true
export INDEX_DIR=/app/index
export PORT=8000
exec "$@"
