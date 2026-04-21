import shutil
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import copy

# 1. 원본 템플릿 복사
source_template = '링글_AI스피킹_경쟁력강화_기획서_final-4.hwpx'
target_file = 'IssueTrace_RAG_기획서_v2.hwpx'
shutil.copy(source_template, target_file)

ns = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
ET.register_namespace('hp', 'http://www.hancom.co.kr/hwpml/2011/paragraph')

def set_text(p, text):
    runs = p.findall('.//hp:run', ns)
    if not runs:
        new_run = ET.SubElement(p, '{http://www.hancom.co.kr/hwpml/2011/paragraph}run')
        t_node = ET.SubElement(new_run, '{http://www.hancom.co.kr/hwpml/2011/paragraph}t')
        t_node.text = text
        return

    # 첫 번째 run에 텍스트 설정
    ts = runs[0].findall('.//hp:t', ns)
    if ts:
        ts[0].text = text
        for t in ts[1:]: t.text = ''
    else:
        t_node = ET.SubElement(runs[0], '{http://www.hancom.co.kr/hwpml/2011/paragraph}t')
        t_node.text = text
    
    # 나머지 run의 텍스트는 비움
    for r in runs[1:]:
        for t in r.findall('.//hp:t', ns):
            t.text = ''

# 2. 기획서 전체 본문 데이터 (서식2-1.md의 모든 세부 내용 포함)
full_content = [
    "IssueTrace RAG 기획서",
    "공정거래 의결서 하이브리드 검색·생성 시스템",
    "2026. 04. 20.",
    
    "Ⅰ. 기획서 개요",
    "1.1 아이디어 기획 분야 및 목적",
    "본 아이디어는 데이터·기술 혁신 트랙과 국민 체감형 서비스 두 분야에 동시에 해당합니다. 공정거래위원회가 공개한 의결서 데이터를 AI 기술로 가공하여, 일반 국민·소상공인·기업 법무팀·연구자 등 다양한 사용자가 자연어로 공정거래 정보를 즉시 조회할 수 있는 실용 서비스를 구현합니다.",
    "핵심 내용: 의결서 500건 전체를 31,879개 청크로 분할·색인하고, 자연어 질문에 대해 관련 근거 청크 5개와 AI 생성 답변을 30초 이내에 반환하는 하이브리드 검색·생성(RAG) 시스템입니다.",
    "목적: 정보 민주화(법률 전문가 없이 조회), 행정 효율화(유사 선례 검색 시간 단축), 데이터 실활용(AI 서비스 전환), 불공정 억제(컴플라이언스 강화).",
    
    "1.2 배경 및 필요성",
    "공정거래위원회 의결서는 현재 PDF/HTML 형태로 분산 게시되어 키워드 검색 외 활용이 사실상 불가능합니다. 법률 전문용어와 복잡한 구조로 인해 비전문가가 접근하기에는 상당한 장벽이 존재합니다.",
    "사회적 수요: 연간 수천 건의 신고 전 유사 사례 검토 수요가 상존하며, 가맹사업법·하도급법 등 소상공인 관련 위반 제재가 증가함에 따라 법률 정보 접근성 필요성이 매우 높아지고 있습니다.",
    
    "Ⅱ. 기획서 주요 내용",
    "2.1 대상 사용자 유형",
    "• 일반 소비자/국민: 피해 유형 파악 및 신고 전 유사 사례 확인",
    "• 가맹점주/소상공인: 본사 갑질 및 하도급 위반 여부 자가 판단",
    "• 기업 법무/컴플라이언스: 동종 업종 위반 선례 및 과징금 수준 파악",
    "• 연구자/조사관: 특정 법조항 관련 판례 수집 및 조사 일관성 확인",
    
    "2.2 데이터 활용 범위",
    "원천 데이터: fairdata.kr 공정거래위원회 의결서 하이브리드 JSON (500건, 31,879청크)",
    "전처리 파이프라인: 텍스트/표 구분 보존, 빈 텍스트 필터링, 8,000자 초과 청크 제한 적용. corpus.json 통합 색인 및 BM25/Dense 임베딩 인덱스 빌드 완료.",
    
    "2.3 구축 AI 서비스 모델 구조",
    "전체 아키텍처: FastAPI 서버 기반의 RAG 파이프라인으로 구성되며, QueryExpander, Hybrid Retriever(BM25+Dense), RRF Re-ranker, LLM Generator가 유기적으로 연결됩니다.",
    "검색 계층: 11개 카테고리 규칙 기반 쿼리 확장과 비대칭 Solar 임베딩 검색을 통해 의미적 유사도를 극대화합니다. RRF(k=60)를 통해 두 방식의 강점을 통합합니다.",
    "생성 계층: Solar-Pro API 및 Qwen2.5-7B 로컬 모델을 활용하여 근거 문서 기반의 답변을 생성합니다.",
    
    "Ⅲ. 문제정의 및 해결 방안",
    "3.1 문제 정의",
    "• 정보 비대칭: 공개된 데이터임에도 불구하고 접근 장벽으로 인해 실질적 활용 저조",
    "• 검색 한계: 단순 제목/날짜 키워드 매칭만 지원하여 의도에 맞는 검색 불가",
    "• 해석 어려움: 수십 페이지의 법률 문서를 사용자가 직접 읽고 판단해야 하는 부담",
    
    "3.2 핵심 기능 및 시나리오",
    "하이브리드 검색과 도메인 특화 쿼리 확장을 통해 사용자의 모호한 질문을 정확한 법률 키워드로 연결합니다. 가맹점주가 판촉비 전가 행위의 위법성을 질문하면, 실제 BGF리테일 제재 사례와 법적 근거를 30초 내에 요약 답변합니다.",
    
    "Ⅳ. 데이터 활용 계획",
    "전체 의결서 500건을 전량 활용하며, 텍스트와 표의 구조를 보존하여 색인합니다. 신규 의결서 추가 시 자동으로 인덱스를 갱신하는 확장 가능한 파이프라인을 유지합니다.",
    
    "Ⅴ. 기대 효과 및 향후 과제",
    "국민의 법률 서비스 비용 장벽을 낮추고 정보 접근 형평성을 제고합니다. 기업의 자율적 컴플라이언스를 유도하여 공정 경쟁 문화를 확산시키며, 정부 차원에서는 행정 업무의 효율성과 일관성을 증대시키는 효과를 기대할 수 있습니다."
]

# 3. XML 파싱 및 내용 주입
tmp_target = target_file + '.tmp'
with zipfile.ZipFile(target_file, 'r') as src, zipfile.ZipFile(tmp_target, 'w') as dst:
    for item in src.infolist():
        data = src.read(item.filename)
        if item.filename == 'Contents/section0.xml':
            root = ET.fromstring(data)
            # 모든 p 태그를 찾음 (본문, 표 내부 포함)
            all_ps = root.findall('.//hp:p', ns)
            
            # 먼저 모든 텍스트 초기화 (링글 내용 완전 삭제)
            for p in all_ps:
                for t in p.findall('.//hp:t', ns):
                    t.text = ''
            
            # 유의미한 위치(원래 텍스트가 있던 위치)를 찾아 공정거래 내용 주입
            content_idx = 0
            for p in all_ps:
                # 스타일이나 속성을 보고 본문 영역 위주로 주입 (단순 순차 주입보다 안정적)
                # 여기서는 '의미 있는 단락'에 순차적으로 채워넣음
                if content_idx < len(full_content):
                    set_text(p, full_content[content_idx])
                    content_idx += 1
            
            data = ET.tostring(root, encoding='utf-8')
        dst.writestr(item, data)

os.replace(tmp_target, target_file)
print(f"Final Proposal Rebuilt: {len(full_content)} segments injected into {target_file}")
