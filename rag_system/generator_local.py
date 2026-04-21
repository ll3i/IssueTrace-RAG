"""
로컬 LLM 기반 답변 생성 모듈
오프라인 평가 환경용 — transformers 라이브러리로 Qwen2.5-7B-Instruct 실행

설정:
  LOCAL_MODEL_PATH  : 모델 파일 경로 (기본: /models/Qwen2.5-7B-Instruct)
  LOCAL_MAX_NEW_TOKENS : 최대 생성 토큰 (기본: 512)
"""
import sys
import time
from typing import List, Dict, Any

sys.stdout.reconfigure(encoding="utf-8")

import config

SYSTEM_PROMPT = """당신은 공정거래위원회 의결서 전문 AI 어시스턴트입니다.

규칙:
1. 반드시 제공된 의결서 청크의 내용만을 근거로 답변하세요.
2. 청크에 없는 내용을 추측하거나 만들어내지 마세요.
3. 핵심 사실, 위반 행위, 조치 내용을 명확하고 간결하게 설명하세요.
4. 법률 용어는 정확하게 사용하되, 이해하기 쉽게 설명하세요.
5. 답변이 불충분할 경우 "제공된 자료에서 확인할 수 없습니다"라고 명시하세요."""

_tokenizer = None
_model = None


def _load_model():
    """로컬 모델을 처음 호출 시 한 번만 로드합니다."""
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    model_path = config.LOCAL_MODEL_PATH
    print(f"[LocalLLM] 모델 로드 중: {model_path}")
    t0 = time.time()

    _tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        padding_side="left",
    )
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    _model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    _model.eval()

    print(f"[LocalLLM] 로드 완료 ({time.time() - t0:.1f}s)")
    return _tokenizer, _model


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        doc_title = meta.get("doc_title", "")
        section = meta.get("section", "")
        text = chunk.get("text", "")

        label = f"[청크 {i}"
        if doc_title:
            label += f" | {doc_title}"
        if section:
            label += f" | {section}"
        label += "]"
        parts.append(f"{label}\n{text}")

    return "\n\n---\n\n".join(parts)


def generate_answer_local(
    query: str,
    chunks: List[Dict[str, Any]],
    max_new_tokens: int = config.LOCAL_MAX_NEW_TOKENS,
    temperature: float = config.TEMPERATURE,
) -> str:
    """
    로컬 LLM으로 답변을 생성합니다.

    Args:
        query: 사용자 질문
        chunks: 검색된 청크 목록 (최대 5개)
        max_new_tokens: 최대 생성 토큰 수
        temperature: 샘플링 온도 (0이면 greedy)

    Returns:
        생성된 답변 문자열
    """
    if not chunks:
        return "관련 문서를 찾을 수 없습니다."

    import torch

    tokenizer, model = _load_model()

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

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # chat template 적용
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(
        [text],
        return_tensors="pt",
        truncation=True,
        max_length=4096,
    ).to(model.device)

    do_sample = temperature > 0.01
    gen_kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=do_sample,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    if do_sample:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["top_p"] = 0.9

    with torch.no_grad():
        output_ids = model.generate(**gen_kwargs)

    # 입력 토큰 제외하고 생성 부분만 디코딩
    input_len = inputs["input_ids"].shape[1]
    generated = output_ids[0][input_len:]
    answer = tokenizer.decode(generated, skip_special_tokens=True).strip()

    return answer if answer else "답변을 생성할 수 없습니다."


def preload():
    """서버 시작 시 모델을 미리 로드합니다."""
    _load_model()
