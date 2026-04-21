import shutil
import zipfile
import xml.etree.ElementTree as ET
import os
import copy
from datetime import datetime

# 1. 파일 설정
SOURCE_TEMPLATE = '링글_AI스피킹_경쟁력강화_기획서_final-4.hwpx'
TARGET_FILE = 'IssueTrace_RAG_기획서_v2.hwpx'
TEMP_FILE = TARGET_FILE + '.tmp'

# 네임스페이스 정의
NS = {
    'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'hs': 'http://www.hancom.co.kr/hwpml/2011/section'
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

# 스타일 맵 (링글 템플릿의 검증된 ID)
STYLE_MAP = {
    'TITLE': {'para': '30', 'char': '17'},
    'SUBTITLE': {'para': '30', 'char': '27'},
    'HEADING1': {'para': '47', 'char': '35'},
    'HEADING2': {'para': '48', 'char': '27'},
    'BODY': {'para': '49', 'char': '16'},
}

def apply_style_and_text(p, text, style_key):
    style = STYLE_MAP.get(style_key, STYLE_MAP['BODY'])
    p.set('paraPrIDRef', style['para'])
    
    # Run 및 Text 노드 처리
    runs = p.findall('.//hp:run', NS)
    if not runs:
        first_run = ET.SubElement(p, '{http://www.hancom.co.kr/hwpml/2011/paragraph}run')
    else:
        first_run = runs[0]
        # 안전한 자식 노드 제거 (루프 중 삭제 방지)
        parent_map = {c: p_node for p_node in p.iter() for c in p_node}
        for r in runs[1:]:
            parent = parent_map.get(r)
            if parent is not None: parent.remove(r)

    first_run.set('charPrIDRef', style['char'])
    
    ts = first_run.findall('.//hp:t', NS)
    if not ts:
        t_node = ET.SubElement(first_run, '{http://www.hancom.co.kr/hwpml/2011/paragraph}t')
        t_node.text = text
    else:
        ts[0].text = text
        for t in ts[1:]: first_run.remove(t)

# 2. 기획서 내용 (서식2-1.md 전문 데이터)
CONTENT_DATA = [
    ('TITLE', 'IssueTrace RAG 기획서'),
    ('SUBTITLE', '공정거래 의결서 하이브리드 검색·생성 시스템'),
    ('SUBTITLE', datetime.now().strftime('%Y. %m. %d.')),
    
    ('HEADING1', 'Ⅰ. 기획서 개요'),
    ('HEADING2', '1.1 아이디어 기획 분야 및 목적'),
    ('BODY', '• 서비스 분야: 데이터·기술 혁신 트랙 (AI 모델 개발), 국민 체감형 서비스'),
    ('BODY', '• 핵심 내용: 공정거래위원회 의결서 500건(31,879개 청크)을 하이브리드 RAG 시스템으로 구축'),
    ('BODY', '• 기술 요약: BM25 희소 검색 + Solar Dense 임베딩 검색 + RRF 통합 재정렬 아키텍처'),
    ('BODY', '• 목적: 정보 민주화(자연어 조회), 행정 효율화, 데이터 실활용, 불공정 행위 억제'),
    
    ('HEADING2', '1.2 배경 및 필요성'),
    ('BODY', '• 제안 배경: 의결서의 분산 게시(PDF/HTML)로 인한 통합 검색 불가 및 높은 법률 전문성 장벽'),
    ('BODY', '• 사회적 수요: 연간 수천 건의 신고 사례 분석 수요 및 소상공인의 법률 정보 접근권 보장'),
    ('BODY', '• 필요성 요약: 기존 분산 게시 자료를 31,879청크로 통합 색인하여 누구나 30초 내 정보 획득 지원'),
    
    ('HEADING2', '1.3 아이디어 결과 내용 요약'),
    ('BODY', '• 구축 결과: 의결서 500건 전량 색인, Solar Large 4,096차원 임베딩, NumPy 기반 고속 벡터 검색'),
    ('BODY', '• 시스템 흐름: 사용자 질문 → 쿼리 확장(11개 카테고리) → 하이브리드 검색 → RRF 통합 → LLM 답변'),
    
    ('HEADING1', 'Ⅱ. 기획서 주요 내용'),
    ('HEADING2', '2.1 대상 사용자 유형'),
    ('BODY', '• 일반 국민: 피해 유형 파악 및 공정위 신고 전 유사 제재 사례 즉시 확인'),
    ('BODY', '• 가맹점주: 본사 갑질 및 하도급법 위반 여부 자가 판단 및 유사 과징금 수준 비교'),
    ('BODY', '• 기업 법무: 동종 업종 위반 선례 및 컴플라이언스 기준 사전 점검을 통한 리스크 관리'),
    ('BODY', '• 조사관: 유사 선례 검색 및 과거 의결의 일관성 확인을 통한 사건 조사 효율화'),
    
    ('HEADING2', '2.2 데이터 활용 범위'),
    ('BODY', '• 원천 데이터: fairdata.kr 공정거래위원회 의결서 하이브리드 JSON (텍스트+표 구분)'),
    ('BODY', '• 전처리: 10자 미만 필터링, 8,000자 초과 청크 제한 적용 및 풍부한 메타데이터(doc_title 등) 부착'),
    
    ('HEADING2', '2.3 구축 AI 서비스 모델 구조'),
    ('BODY', '• 검색 계층: 90여 개 법률 용어 사전을 활용한 쿼리 확장 및 비대칭 Solar 임베딩(Passage/Query)'),
    ('BODY', '• 생성 계층: Solar-Pro API(개발용) 및 Qwen2.5-7B 로컬 모델(14.1GB Docker 번들) 활용'),
    
    ('HEADING1', 'Ⅲ. 문제정의 및 해결 방안'),
    ('HEADING2', '3.1 핵심 문제 및 해결 방안'),
    ('BODY', '• 문제: "있어도 못 쓰는 데이터(정보 비대칭)", "뭘 검색할지 모름(키워드 한계)", "찾아도 읽기 어려움"'),
    ('BODY', '• 해결: 하이브리드 RAG를 통한 자연어 의미 검색 지원 및 Top-5 근거 기반 LLM 요약 답변 제공'),
    
    ('HEADING2', '3.2 서비스 시나리오'),
    ('BODY', '• 시나리오 1: 편의점 가맹점주의 판촉비 전가 위법성 확인 (BGF리테일 제재 사례 및 법적 근거 제시)'),
    ('BODY', '• 시나리오 2: 기업 법무팀의 가격 담합 과징금 산정 기준 조회 및 유사 선례 분석'),
    
    ('HEADING1', 'Ⅳ. 데이터 활용 계획'),
    ('BODY', '• 원칙: 전량 활용, 문서 구조(Text/Table) 보존, 지속 확장 가능한 자동화 파이프라인 유지'),
    ('BODY', '• 평가 대응: 200개 평가 질문에 대해 BM25(정확 매칭)와 Dense(의미 검색)의 시너지를 통한 대응'),
    
    ('HEADING1', 'Ⅴ. 기대 효과'),
    ('BODY', '• 국민: 법률 자문 비용 절감 및 정보 접근 형평성 제고, 소비자 권리 및 사회적 신뢰 강화'),
    ('BODY', '• 기업: 리스크 조기 감지 및 컴플라이언스 비용 절감, 시장의 공정 경쟁 문화 촉진'),
    ('BODY', '• 정부: 공정위 행정 효율화, 데이터 활용 실증 모델 제시 및 정책 인텔리전스 강화'),
    
    ('HEADING1', 'Ⅵ. 기타 사항'),
    ('BODY', '• 향후 과제: 심결·고시·예규로의 데이터셋 확장 및 Cross-Encoder 기반 Reranker 고도화 예정')
]

def rebuild_hwpx():
    shutil.copy(SOURCE_TEMPLATE, TARGET_FILE)
    
    with zipfile.ZipFile(TARGET_FILE, 'r') as src, zipfile.ZipFile(TEMP_FILE, 'w') as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == 'Contents/section0.xml':
                root = ET.fromstring(data)
                all_ps = root.findall('.//hp:p', NS)
                
                # 스타일 샘플링
                samples = {
                    'TITLE': next((p for p in all_ps if p.get('paraPrIDRef') == '30'), all_ps[0]),
                    'HEADING1': next((p for p in all_ps if p.get('paraPrIDRef') == '47'), all_ps[0]),
                    'HEADING2': next((p for p in all_ps if p.get('paraPrIDRef') == '48'), all_ps[0]),
                    'BODY': next((p for p in all_ps if p.get('paraPrIDRef') == '49'), all_ps[0]),
                }
                
                # 기존 텍스트 초기화
                for p in all_ps:
                    for t in p.findall('.//hp:t', NS): t.text = ''
                
                # 주입 섹션 찾기
                body_element = root.find('.//hs:sec', NS)
                if body_element is None: body_element = root
                
                content_idx = 0
                # 기존에 존재하는 p 태그들에 우선 채움
                for p in all_ps:
                    if content_idx < len(CONTENT_DATA):
                        tag, text = CONTENT_DATA[content_idx]
                        apply_style_and_text(p, text, tag)
                        content_idx += 1
                
                # 부족하면 복제하여 추가
                while content_idx < len(CONTENT_DATA):
                    tag, text = CONTENT_DATA[content_idx]
                    sample = samples.get(tag, samples['BODY'])
                    new_p = copy.deepcopy(sample)
                    apply_style_and_text(new_p, text, tag)
                    body_element.append(new_p)
                    content_idx += 1
                
                data = ET.tostring(root, encoding='utf-8')
            dst.writestr(item, data)
            
    os.replace(TEMP_FILE, TARGET_FILE)
    print("IssueTrace RAG Full Proposal Generated Successfully.")

if __name__ == "__main__":
    rebuild_hwpx()
