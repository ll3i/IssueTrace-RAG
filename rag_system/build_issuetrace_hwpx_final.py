import copy
import pathlib
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime

BASE_DIR = pathlib.Path(__file__).resolve().parent
SOURCE_PATH = BASE_DIR / "IssueTrace_RAG_기획서_v2.hwpx"
TARGET_PATH = BASE_DIR / "IssueTrace_RAG_기획서_v2.hwpx"
TEMP_PATH = BASE_DIR / "IssueTrace_RAG_기획서_v2_final.tmp.hwpx"

NS = {
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

def set_paragraph_text(paragraph, text, char_pr_id=None):
    # 기존 run 구조를 유지하면서 텍스트만 교체
    runs = paragraph.findall("hp:run", NS)
    if not runs:
        run = ET.SubElement(paragraph, f"{{{NS['hp']}}}run")
        if char_pr_id: run.set("charPrIDRef", char_pr_id)
    else:
        run = runs[0]
        for r in runs[1:]: paragraph.remove(r)
        for child in list(run):
            if child.tag == f"{{{NS['hp']}}}t": run.remove(child)
    
    t = ET.SubElement(run, f"{{{NS['hp']}}}t")
    t.text = text

def create_proposal_content():
    content = [
        ("TITLE", "IssueTrace RAG 기획서"),
        ("SUBTITLE", "공정거래 의결서 하이브리드 검색·생성 시스템"),
        ("DATE", datetime.now().strftime("%Y. %m. %d.")),
        ("HEADING1", "Ⅰ. 서비스 개요 및 제안 배경"),
        ("HEADING2", "1.1 서비스 분야 및 목적"),
        ("BODY", "본 서비스는 공정거래위원회 의결서 데이터를 AI 기술로 가공하여, 일반 국민과 기업이 자연어로 공정거래 정보를 즉시 조회할 수 있는 'IssueTrace RAG' 시스템입니다."),
        ("BODY", "목적: 정보 민주화(누구나 조회), 행정 효율화(조사관 선례 검색), 데이터 실활용(공개 데이터의 AI 서비스화)."),
        ("HEADING2", "1.2 제안 배경 및 사회적 필요성"),
        ("BODY", "현재 의결서는 PDF/HTML로 분산 게시되어 있어 키워드 검색 외 활용이 어렵고 전문용어 장벽이 높습니다. 소상공인의 법률 정보 접근권 보장과 기업의 컴플라이언스 강화를 위해 AI 기반의 지능형 검색이 필수적입니다."),
        
        ("HEADING1", "Ⅱ. IssueTrace RAG: 5대 핵심 기술 및 가치"),
        ("HEADING2", "[가치 1] 하이브리드 검색 (BM25 + Dense)"),
        ("BODY", "정확한 키워드 매칭(BM25)과 의미적 유사도 검색(Dense)을 결합하여 법률 고유명사와 맥락을 동시에 파악하는 최적의 검색 품질을 제공합니다."),
        ("HEADING2", "[가치 2] 도메인 특화 쿼리 확장"),
        ("BODY", "11개 카테고리 90여 개 법률 전문 용어 사전을 내장하여, 일반인의 구어체 질문을 전문적인 법률 검색 쿼리로 자동 확장합니다."),
        ("HEADING2", "[가치 3] 비대칭 임베딩 및 NumPy 벡터 저장"),
        ("BODY", "문서와 질의에 최적화된 비대칭 임베딩 전략을 채택하고, NumPy 기반 자체 벡터 저장소를 구축하여 외부 DB 없이 오프라인에서도 고속 검색이 가능합니다."),
        ("HEADING2", "[가치 4] 근거 기반 LLM 답변 생성"),
        ("BODY", "검색된 Top-5 청크만을 근거로 답변을 생성하여 할루시네이션을 방지하고, 답변의 신뢰성을 투명하게 공개합니다."),
        ("HEADING2", "[가치 5] 직관적 웹 대시보드 및 UX"),
        ("BODY", "예시 질문 칩, 단계별 진행 표시, 근거 청크 카드 및 상세 모달 등 사용자 친화적인 인터페이스를 통해 복잡한 정보를 한눈에 파악할 수 있게 합니다."),
        
        ("HEADING1", "Ⅲ. 기술적 구현 방안 및 로드맵"),
        ("HEADING2", "3.1 시스템 아키텍처"),
        ("BODY", "FastAPI 서버를 중심으로 QueryExpander, Hybrid Retriever, RRF Re-ranker, LLM Generator가 유기적으로 연결된 모듈형 아키텍처를 가집니다."),
        ("HEADING2", "3.2 데이터 파이프라인 및 전처리"),
        ("BODY", "500건의 의결서를 31,879개 청크로 분할하고, 텍스트와 표를 구분하여 메타데이터와 함께 색인하는 자동화 파이프라인을 구축했습니다."),
        ("HEADING2", "3.3 오프라인 배포 및 보안 전략"),
        ("BODY", "Qwen2.5-7B 모델을 포함한 14.1GB 규모의 Docker 이미지를 통해 폐쇄망 환경에서도 인터넷 연결 없이 완전한 동작을 보장합니다."),
        
        ("HEADING1", "Ⅳ. 기대 효과 및 성과 지표"),
        ("HEADING2", "4.1 정량적/정성적 기대 효과"),
        ("BODY", "정량적: Recall@5 0.70 이상, 응답 시간 20초 이내 달성. 정성적: 법률 정보 접근성 향상 및 공정 경쟁 문화 확산."),
        ("HEADING2", "4.2 페르소나별 활용 시나리오"),
        ("BODY", "소상공인: 가맹본부 갑질 여부 확인. 기업: 담합 과징금 리스크 사전 진단. 연구자: 특정 판례 및 조문 해석 사례 수집."),
        
        ("HEADING1", "Ⅴ. 추진 계획 및 기타 사항"),
        ("BODY", "향후 심결·고시·예규 등으로 데이터셋을 확장하고, Cross-Encoder 기반 Reranker 적용을 통해 검색 정확도를 지속적으로 고도화할 계획입니다.")
    ]
    return content

def update_hwpx():
    proposal_data = create_proposal_content()
    
    with zipfile.ZipFile(SOURCE_PATH, "r") as source, zipfile.ZipFile(TEMP_PATH, "w") as dest:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "Contents/section0.xml":
                root = ET.fromstring(data)
                paragraphs = root.findall(".//hp:p", NS)
                
                # 기존 단락들 중 일부를 활용하거나 새로 생성
                # 여기서는 간단히 기존 단락들을 순회하며 내용을 덮어쓰고, 모자라면 추가함
                for i, (tag, text) in enumerate(proposal_data):
                    if i < len(paragraphs):
                        p = paragraphs[i]
                        # 스타일 구분을 위해 Heading 등에 따라 charPrIDRef 조절 가능 (생략)
                        set_paragraph_text(p, text)
                    else:
                        # 새 단락 추가 (기본 스타일 복사)
                        new_p = copy.deepcopy(paragraphs[0])
                        set_paragraph_text(new_p, text)
                        root.append(new_p)
                
                # 남는 단락 제거
                # 루트 혹은 부모 요소에서 안전하게 삭제
                parent_map = {c: p for p in root.iter() for c in p}
                for p in paragraphs[len(proposal_data):]:
                    parent = parent_map.get(p)
                    if parent is not None:
                        parent.remove(p)
                
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            
            dest.writestr(info, data)

    TEMP_PATH.replace(TARGET_PATH)
    print(f"Successfully updated {TARGET_PATH}")

if __name__ == "__main__":
    update_hwpx()
