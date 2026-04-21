# IssueTrace RAG 기획서 시각화 요약

## 핵심 수치
- 의결서 원천 건수: 500건
- 전체 청크 수: 31,879개
- 사건당 평균 청크 수: 63.76개
- 사건당 중앙 청크 수: 43개
- 피심인 정보 평균 건수: 5.26명
- 청크 구성: text 21,111개 (66.2%), table 10,768개 (33.8%)

## 권장 삽입 시각화
- `01_cases_by_year.png`: 공개 연도별 의결서 건수. 데이터 축적 규모를 가장 직관적으로 보여줌.
- `02_violation_type_top10.png`: 피심인 기준 주요 위반유형 Top 10. 서비스가 어떤 법률 수요에 집중되는지 설명하기 좋음.
- `03_action_type_distribution.png`: 주요 조치유형 분포. 시정명령/과징금 중심의 활용 가치를 강조할 수 있음.
- `04_chunk_composition.png`: text/table 청크 비중. 근거 기반 RAG에서 텍스트와 표 데이터를 함께 살린다는 점을 설명하기 좋음.
- `05_chunk_count_distribution.png`: 사건별 청크 수 분포. 문서 길이 편차가 큰 법률 문서에서도 검색이 동작한다는 점을 보여줌.
- `06_top10_longest_cases.png`: 청크 수 기준 상위 10개 사건. 대형 의결서 처리 역량을 어필할 때 사용 가능.

## 서술용 포인트
- 공개 연도별로는 2020년 58건, 2021년 6건, 2022년 240건, 2023년 47건, 2024년 73건, 2025년 61건, 2026년 15건로 구성되어 있어, 단년도 샘플이 아닌 다년도 법률 데이터셋임을 설명할 수 있음.
- 위반유형은 부당한 공동행위(1,480건), 불공정하도급거래행위(271건), 전자상거래소비자보호법령 위반(204건) 순으로 나타나 공정거래 핵심 쟁점을 넓게 포괄함.
- 조치유형은 시정명령(1,239건)과 과징금(1,059건)이 대다수여서, 실제 규제/제재 판단 지원 사례를 강조하기 좋음.
- 사건당 청크 수는 최소 8개, 최대 830개로 편차가 크며, 상위 사건은 조달청 발주 건설사업관리용역 입찰...(830개), 11개 초박막액정표시장치(TFT-...(551개), 13개 비료 제조ㆍ판매사의 부당한...(453개)로 집계됨.

## 산출물 목록
- `proposal_visuals/01_cases_by_year.png`
- `proposal_visuals/02_violation_type_top10.png`
- `proposal_visuals/03_action_type_distribution.png`
- `proposal_visuals/04_chunk_composition.png`
- `proposal_visuals/05_chunk_count_distribution.png`
- `proposal_visuals/06_top10_longest_cases.png`
- `proposal_visuals/aggregate_metrics.json`
- `proposal_visuals/cases_by_year.csv`
- `proposal_visuals/violation_type_top10.csv`
- `proposal_visuals/action_type_distribution.csv`
