# IssueTrace RAG: 공정거래 의결서 쟁점 추출 기반 질의응답 모델

제2회 공정위 AI·데이터 활용 공모전 **Track 2 (AI 모델 개발)** 출품작입니다.
공정거래위원회 의결서 데이터를 기반으로 사용자의 질의에 대해 신속하고 정확하게 관련 근거를 탐색하고, 신뢰도 높은 답변을 생성하는 Hybrid RAG(Retrieval-Augmented Generation) 시스템입니다.

## 📌 주요 특징
- **Hybrid Retrieval**: BM25(Sparse)와 Dense Embedding 검색을 혼합하여 법률 용어의 정밀성과 의미 유사성을 동시에 고려합니다.
- **RRF(Reciprocal Rank Fusion)**: 검색 결과를 정밀하게 재정렬하여 Top 5 청크의 품질을 극대화합니다.
- **근거 중심 질의응답**: 검색된 의결서 청크만을 기반으로 답변을 생성하여 할루시네이션(환각)을 방지합니다.
- **오프라인 평가 지원**: 외부 API 사용이 제한된 평가 환경을 위해 로컬 LLM(Qwen2.5-7B) 구동 및 오프라인 처리를 완벽하게 지원합니다.

## 📁 프로젝트 구조
- `rag_system/`: RAG 파이프라인, FastAPI 서버, 검색 및 생성 모듈이 포함된 메인 소스코드 디렉토리입니다. ([상세 README 확인](rag_system/README.md))
- `AI활용데이터/`: (Git 제외) 의결서 원본, 청킹 메타데이터 및 hybrid.json 파일 등 대회 제공 데이터셋이 위치하는 폴더입니다.

## 🚀 시작하기

자세한 아키텍처, 인덱스 구축 과정, 로컬 개발 환경 실행 방법 및 Docker 제출 이미지 빌드 가이드는 `rag_system/` 디렉토리 내의 README를 참고해주세요.

```bash
cd rag_system
pip install -r requirements.txt
python server.py
```

## 📝 평가 지표 최적화 전략
- **Recall@5 & MRR**: Hybrid Retrieval과 Reranker 파이프라인을 통해 정답 청크가 최상위에 노출되도록 튜닝되었습니다.
- **BERTScore & F1**: 로컬/API LLM에 특화된 요약 템플릿을 사용하여 정답 문장과의 의미 및 토큰 일치율을 안정적으로 향상시킵니다.
