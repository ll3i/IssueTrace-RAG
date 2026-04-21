import copy
import pathlib
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime

BASE_DIR = pathlib.Path(__file__).resolve().parent
SOURCE_PATH = BASE_DIR / "IssueTrace_RAG_기획서_v2.hwpx"
TARGET_PATH = BASE_DIR / "IssueTrace_RAG_기획서_v2.hwpx"
TEMP_PATH = BASE_DIR / "IssueTrace_RAG_기획서_v2_style_fix.tmp.hwpx"

NS = {
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
}

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

# 분석된 스타일 매핑
STYLES = {
    "TITLE": {"para": "30", "char": "17"},
    "SUBTITLE": {"para": "30", "char": "27"},
    "DATE": {"para": "30", "char": "27"},
    "HEADING1": {"para": "47", "char": "35"},
    "HEADING2": {"para": "48", "char": "27"},
    "BODY": {"para": "49", "char": "16"},
}

def set_paragraph_style_and_text(paragraph, text, style_type):
    style = STYLES.get(style_type, STYLES["BODY"])
    paragraph.set("paraPrIDRef", style["para"])
    
    runs = paragraph.findall("hp:run", NS)
    for r in runs: paragraph.remove(r)
    
    run = ET.SubElement(paragraph, f"{{{NS['hp']}}}run", {"charPrIDRef": style["char"]})
    t = ET.SubElement(run, f"{{{NS['hp']}}}t")
    t.text = text

def create_refined_content():
    return [
        ("TITLE", "IssueTrace RAG 기획서"),
        ("SUBTITLE", "공정거래 의결서 하이브리드 검색·생성 시스템"),
        ("DATE", datetime.now().strftime("%Y. %m. %d.")),
        
        ("HEADING1", "Ⅰ. 서비스 개요 및 제안 배경"),
        ("HEADING2", "1.1 서비스 개요"),
        ("BODY", "• 공정거래위원회 의결서 500건을 AI 기술로 가공하여 하이브리드 RAG 시스템 구축"),
        ("BODY", "• 자연어 질의를 통한 즉각적인 법률 위반 선례 및 제재 결과 조회 서비스 제공"),
        ("HEADING2", "1.2 제안 배경 및 필요성"),
        ("BODY", "• 기존 의결서의 분산 게시 및 전문 용어 장벽으로 인한 정보 접근성 저하 문제 해결"),
        ("BODY", "• 소상공인 권리 보호 및 기업의 선제적 컴플라이언스 강화 도구 필요성 증대"),
        
        ("HEADING1", "Ⅱ. IssueTrace RAG: 5대 핵심 기술 가치"),
        ("HEADING2", "[가치 1] 하이브리드 검색 엔진 (Hybrid Search)"),
        ("BODY", "• BM25(키워드)와 Solar Dense(의미) 검색을 결합하여 고유명사와 맥락 동시 파악"),
        ("HEADING2", "[가치 2] 법률 도메인 특화 쿼리 확장"),
        ("BODY", "• 11개 카테고리 90여 개 전문 용어 사전을 통한 구어체 질문의 법률 최적화"),
        ("HEADING2", "[가치 3] 고성능 오프라인 벡터 저장소"),
        ("BODY", "• NumPy 기반 자체 벡터 엔진 구축으로 외부 DB 없이도 밀리초 단위 검색 수행"),
        ("HEADING2", "[가치 4] 근거 투명성 기반 답변 생성"),
        ("BODY", "• 검색된 Top-5 청크만을 활용한 요약 답변 생성으로 할루시네이션(환각) 방지"),
        ("HEADING2", "[가치 5] 사용자 중심 인텔리전트 UX"),
        ("BODY", "• 단계별 진행 표시바, 근거 문서 카드 UI, Chunk ID 복사 등 편의 기능 강화"),
        
        ("HEADING1", "Ⅲ. 상세 구현 및 보안 전략"),
        ("HEADING2", "3.1 시스템 아키텍처"),
        ("BODY", "• FastAPI 기반 비동기 서버와 Qwen2.5-7B 로컬 LLM의 유기적 통합"),
        ("HEADING2", "3.2 오프라인 배포 및 보안"),
        ("BODY", "• 14.1GB 규모의 Docker 이미지 번들링으로 폐쇄망 환경에서 완전한 보안 보장"),
        
        ("HEADING1", "Ⅳ. 기대 효과"),
        ("HEADING2", "4.1 국민 및 기업 관점"),
        ("BODY", "• 일반인의 법률 자문 비용 절감 및 기업의 리스크 사전 감지 효과"),
        ("HEADING2", "4.2 정량적 성과 목표"),
        ("BODY", "• 검색 정확도(Recall@5) 0.70 이상 및 전체 응답 시간 30초 이내 준수"),
        
        ("HEADING1", "Ⅴ. 향후 발전 계획"),
        ("BODY", "• 심결, 고시 등 데이터셋 확장 및 Cross-Encoder 기반 Reranker 고도화 예정")
    ]

def update_hwpx_with_style():
    refined_data = create_refined_content()
    
    with zipfile.ZipFile(SOURCE_PATH, "r") as source, zipfile.ZipFile(TEMP_PATH, "w") as dest:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "Contents/section0.xml":
                root = ET.fromstring(data)
                parent_map = {c: p for p in root.iter() for c in p}
                paragraphs = root.findall(".//hp:p", NS)
                
                # 기존 스타일 샘플 저장
                sample_p = copy.deepcopy(paragraphs[0])
                
                # 내용 업데이트 및 스타일 적용
                for i, (style_tag, text) in enumerate(refined_data):
                    if i < len(paragraphs):
                        p = paragraphs[i]
                        set_paragraph_style_and_text(p, text, style_tag)
                    else:
                        new_p = copy.deepcopy(sample_p)
                        set_paragraph_style_and_text(new_p, text, style_tag)
                        root.append(new_p)
                
                # 남는 단락 제거
                for p in paragraphs[len(refined_data):]:
                    parent = parent_map.get(p)
                    if parent is not None: parent.remove(p)
                
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            
            dest.writestr(info, data)

    TEMP_PATH.replace(TARGET_PATH)
    print(f"Successfully updated with clean styles: {TARGET_PATH}")

if __name__ == "__main__":
    update_hwpx_with_style()
