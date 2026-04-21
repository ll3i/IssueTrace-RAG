"""
근거 기반 답변 생성 모듈
검색된 5개 청크를 컨텍스트로 LLM이 답변을 생성합니다.

핵심 원칙:
  - 검색된 청크 범위 내에서만 답변 생성 (환각 방지)
  - 핵심 사실·법리·조치 결과를 간결하게 요약
  - 응답 시간 30초 제한 고려 → 경량 모델 사용

모드 선택 (config / 환경변수):
  - OFFLINE_MODE=true  → 로컬 LLM 사용 (평가 환경)
  - USE_LOCAL_LLM=true → 로컬 LLM 사용
  - 그 외              → Solar API / OpenAI API 사용 (개발 환경)
"""
import sys
from typing import List, Dict, Any

sys.stdout.reconfigure(encoding="utf-8")

from openai import OpenAI
import config


# ── 프롬프트 ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 공정거래위원회 의결서 전문 AI 어시스턴트입니다.

규칙:
1. 반드시 제공된 의결서 청크의 내용만을 근거로 답변하세요.
2. 청크에 없는 내용을 추측하거나 만들어내지 마세요.
3. 핵심 사실, 위반 행위, 조치 내용을 명확하고 간결하게 설명하세요.
4. 법률 용어는 정확하게 사용하되, 이해하기 쉽게 설명하세요.
5. 답변이 불충분할 경우 "제공된 자료에서 확인할 수 없습니다"라고 명시하세요."""


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    """청크 목록을 하나의 컨텍스트 문자열로 변환합니다."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        doc_title = meta.get("doc_title", "")
        section = meta.get("section", "")
        header = meta.get("Header", "")
        text = chunk.get("text", "")

        label = f"[청크 {i}"
        if doc_title:
            label += f" | {doc_title}"
        if section or header:
            label += f" | {section or header}"
        label += "]"

        parts.append(f"{label}\n{text}")

    return "\n\n---\n\n".join(parts)


def _get_client() -> tuple[OpenAI, str]:
    """설정에 따라 OpenAI 클라이언트와 모델명을 반환합니다."""
    model = config.GENERATION_MODEL

    if config.UPSTAGE_API_KEY and (model.startswith("solar") or model.startswith("syn")):
        client = OpenAI(
            api_key=config.UPSTAGE_API_KEY,
            base_url="https://api.upstage.ai/v1",
        )
    else:
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 또는 UPSTAGE_API_KEY가 설정되지 않았습니다.")
        client = OpenAI(api_key=config.OPENAI_API_KEY)

    return client, model


def generate_answer(
    query: str,
    chunks: List[Dict[str, Any]],
    max_tokens: int = config.MAX_TOKENS,
    temperature: float = config.TEMPERATURE,
) -> str:
    """
    검색된 청크를 근거로 답변을 생성합니다.

    OFFLINE_MODE / USE_LOCAL_LLM=true 시 로컬 모델 사용,
    그 외에는 Solar API / OpenAI API 사용.
    """
    # ── 로컬 LLM 모드 ──────────────────────────────────────────────────
    if config.USE_LOCAL_LLM:
        from generator_local import generate_answer_local
        return generate_answer_local(query, chunks, temperature=temperature)

    # ── API 모드 (개발 환경) ────────────────────────────────────────────
    if not chunks:
        return "관련 문서를 찾을 수 없습니다."

    context = _build_context(chunks)
    user_message = f"""다음 의결서 청크들을 참고하여 질문에 답변하세요.

## 참고 청크
{context}

## 질문
{query}

## 답변 요구사항
- 위 청크에 있는 내용만 사용
- 위반 행위, 적용 법조항, 조치 결과(시정명령/과징금 등) 포함
- 3-5문장으로 핵심만 간결하게"""

    client, model = _get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    return response.choices[0].message.content.strip()


def generate_answer_streaming(
    query: str,
    chunks: List[Dict[str, Any]],
    max_tokens: int = config.MAX_TOKENS,
):
    """스트리밍 방식으로 답변을 생성합니다 (서버에서 활용)."""
    if not chunks:
        yield "관련 문서를 찾을 수 없습니다."
        return

    context = _build_context(chunks)
    user_message = f"""다음 의결서 청크들을 참고하여 질문에 답변하세요.

## 참고 청크
{context}

## 질문
{query}

답변:"""

    client, model = _get_client()

    with client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
        temperature=config.TEMPERATURE,
        stream=True,
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
