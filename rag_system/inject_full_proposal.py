import shutil
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import copy

# 1. 원본 템플릿 복사 (가장 깔끔한 기반에서 시작)
source_template = '링글_AI스피킹_경쟁력강화_기획서_final-4.hwpx'
target_file = 'IssueTrace_RAG_기획서_v2.hwpx'
shutil.copy(source_template, target_file)

ns = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
ET.register_namespace('hp', 'http://www.hancom.co.kr/hwpml/2011/paragraph')

def set_text(p, text):
    runs = p.findall('.//hp:run', ns)
    if not runs:
        return

    # 스타일 유지를 위해 첫 번째 run만 남기고 나머지의 텍스트는 비움
    for i, run in enumerate(runs):
        ts = run.findall('.//hp:t', ns)
        if i == 0:
            if ts:
                ts[0].text = text
                # 나머지 t 노드의 텍스트는 비움
                for t in ts[1:]: t.text = ''
            else:
                t_node = ET.SubElement(run, '{http://www.hancom.co.kr/hwpml/2011/paragraph}t')
                t_node.text = text
        else:
            # 나머지 run의 모든 t 노드 텍스트 비움
            for t in ts: t.text = ''

# 2. 주입할 공정거래 AI 전체 기획서 내용 (기획서_서식2-1.md 기반)
proposal_content = [
    "IssueTrace RAG 기획서", # 0: 표지 제목
    "공정거래 의결서 하이브리드 검색·생성 시스템", # 1: 표지 부제
    "2026. 04. 20.", # 2: 날짜 (위치는 템플릿 맞춰 조정)
    
    "Ⅰ. 기획서 개요",
    "1.1 서비스 분야 및 목적",
    "• 서비스 분야: 데이터·기술 혁신 트랙 (AI 모델 개발), 국민 체감형 서비스",
    "• 핵심 내용: 공정거래위원회 의결서 500건(31,879개 청크)을 하이브리드 RAG 시스템으로 구축",
    "• 주요 기술: BM25 희소 검색 + Solar Dense 임베딩 검색 + RRF 통합 재정렬 아키텍처",
    "• 구축 목적: 법률 정보 민주화, 행정 효율화, 공개 데이터의 실활용 및 공정 경쟁 환경 조성",
    
    "1.2 배경 및 필요성",
    "• 제안 배경: 의결서의 분산 게시(PDF/HTML)로 인한 통합 검색 불가 및 높은 전문성 장벽",
    "• 사회적 수요: 연간 수천 건의 신고 사례 분석 수요 및 소상공인의 법률 정보 접근성 필요성 증대",
    "• 필요성: 자연어 의미 검색 지원을 통해 누구나 30초 이내에 정확한 제재 선례 정보를 획득 가능",
    
    "Ⅱ. 시스템 아키텍처 및 핵심 기술",
    "2.1 하이브리드 검색 엔진 (Hybrid Search)",
    "• BM25Okapi: 기업명, 법조항 번호 등 고유명사의 정확한 키워드 매칭 수행",
    "• Solar Dense Retrieval: Upstage Solar 임베딩을 통한 질의 의도 및 의미 유사도 검색",
    "• RRF (Reciprocal Rank Fusion): 두 검색 결과의 순위를 통합하여 최적의 근거 청크 5개 선정",
    
    "2.2 도메인 특화 쿼리 확장 (Query Expander)",
    "• 11개 카테고리 90여 개 법률 전문 용어 사전을 활용한 규칙 기반 쿼리 확장(0ms 레이턴시)",
    "• 사용자의 구어체 질문을 법률적으로 정교화하여 검색 정확도를 획기적으로 개선",
    
    "2.3 오프라인 벡터 저장소 및 보안 전략",
    "• NumPy 기반 자체 벡터 엔진 구축: 외부 DB 의존성 없이 로컬 환경에서 밀리초 단위 고속 검색",
    "• 완전 오프라인 배포: 14.1GB 규모의 Docker 이미지에 Qwen2.5-7B 모델 번들링으로 보안 강화",
    
    "Ⅲ. 사용자 경험 및 기대 효과",
    "3.1 지능형 웹 대시보드 (UX)",
    "• 자연어 질문 textarea 및 8개의 예시 질문 칩 제공 (클릭 한 번으로 검색 실행)",
    "• 검색 진행 과정 시각화: 쿼리 확장 → 임베딩 검색 → AI 답변 생성 단계별 표시",
    "• 답변의 투명성: 답변과 함께 제공되는 Top-5 근거 청크 카드 및 상세 모달 제공",
    
    "3.2 정량적 성과 목표 및 기대 효과",
    "• 정량적 성과: Recall@5 0.70 이상 달성, 평균 응답 시간 20초 이내 (GPU 기준)",
    "• 국민 관점: 법률 자문 비용 절감 및 소비자 권리 강화를 통한 사회적 신뢰 제고",
    "• 기업 관점: 리스크 사전 감지 및 컴플라이언스 비용 절감을 통한 공정 경쟁 촉진",
    "• 정부 관점: 공정위 조사관의 유사 선례 검색 시간 단축을 통한 행정 업무 효율화"
]

# 3. 템플릿 XML 파싱 및 전면 텍스트 교체
tmp_target = target_file + '.tmp'
with zipfile.ZipFile(target_file, 'r') as src, zipfile.ZipFile(tmp_target, 'w') as dst:
    for item in src.infolist():
        data = src.read(item.filename)
        if item.filename == 'Contents/section0.xml':
            root = ET.fromstring(data)
            paragraphs = root.findall('.//hp:p', ns)
            
            # 모든 단락을 순회하며 내용 주입
            content_idx = 0
            for i, p in enumerate(paragraphs):
                # 단락에 실제 텍스트가 존재하는지 확인
                texts = ''.join([t.text for t in p.findall('.//hp:t', ns) if t.text])
                if texts.strip():
                    if content_idx < len(proposal_content):
                        # 공정거래 AI 내용 주입
                        set_text(p, proposal_content[content_idx])
                        content_idx += 1
                    else:
                        # 주입할 내용이 끝나면 나머지는 모두 비움 (링글 내용 삭제)
                        set_text(p, '')
            
            # 표(table) 내부의 텍스트도 완전히 비워 링글 잔여 데이터 제거
            for table in root.findall('.//{http://www.hancom.co.kr/hwpml/2011/paragraph}p', ns):
                # 이미 위에서 처리됨 (루트 이하 모든 p를 찾음)
                pass
            
            data = ET.tostring(root, encoding='utf-8')
        dst.writestr(item, data)

os.replace(tmp_target, target_file)
print("Successfully replaced Ringle content with Fair Trade AI content and cleared all residues.")
