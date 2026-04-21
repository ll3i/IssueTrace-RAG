"""
평가 제출 전 로컬 모델 다운로드 스크립트
인터넷이 되는 환경에서 미리 실행하여 models/ 디렉토리에 저장합니다.

실행:
    python download_models.py
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


def download_llm(model_name: str = "Qwen/Qwen2.5-7B-Instruct"):
    """생성 모델 다운로드"""
    save_path = MODELS_DIR / model_name.split("/")[-1]
    if save_path.exists() and any(save_path.iterdir()):
        print(f"[skip] LLM 이미 존재: {save_path}")
        return str(save_path)

    print(f"[download] LLM: {model_name} → {save_path}")
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch

    tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    tok.save_pretrained(str(save_path))

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )
    model.save_pretrained(str(save_path))
    print(f"[done] LLM 저장 완료: {save_path}")
    return str(save_path)


def download_embed(model_name: str = "BAAI/bge-m3"):
    """임베딩 모델 다운로드 (Dense Retriever 로컬 교체용, 선택사항)"""
    save_path = MODELS_DIR / model_name.split("/")[-1]
    if save_path.exists() and any(save_path.iterdir()):
        print(f"[skip] 임베딩 모델 이미 존재: {save_path}")
        return str(save_path)

    print(f"[download] 임베딩 모델: {model_name} → {save_path}")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    model.save(str(save_path))
    print(f"[done] 임베딩 모델 저장 완료: {save_path}")
    return str(save_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--embed", default=None, help="임베딩 모델 (선택사항)")
    parser.add_argument("--skip-embed", action="store_true")
    args = parser.parse_args()

    llm_path = download_llm(args.llm)
    print(f"\n✓ LLM 경로: {llm_path}")
    print(f"  → Dockerfile에서 LOCAL_MODEL_PATH={llm_path} 로 설정하거나")
    print(f"     docker run 시 -v {llm_path}:/models/{args.llm.split('/')[-1]} 마운트")

    if not args.skip_embed and args.embed:
        embed_path = download_embed(args.embed)
        print(f"\n✓ 임베딩 모델 경로: {embed_path}")
