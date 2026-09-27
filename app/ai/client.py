import json
from typing import TypeVar

from anthropic import Anthropic, APIConnectionError
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.core.config import settings

client = Anthropic(api_key=settings.anthropic_api_key, timeout=60)
T = TypeVar("T", bound=BaseModel)


def _strip_fence(text: str) -> str:
    text = text.strip()
    for p in ("```json", "```"):
        text = text.removeprefix(p)
    return text.removesuffix("```").strip()


def ask_json(system: str, user: str, schema: type[T], retries: int = 1) -> T:
    """LLM에 서술만 맡기고, 응답은 Pydantic 스키마로 검증한다."""
    system_prompt = (
        f"{system}\n\n반드시 아래 JSON 스키마에 맞는 JSON만 출력하세요. 다른 텍스트는 쓰지 마세요.\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )
    for _ in range(retries + 1):
        try:
            res = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user}],
            )
        except APIConnectionError:
            raise HTTPException(503, "LLM API에 연결할 수 없습니다.")
        text = "".join(b.text for b in res.content if b.type == "text")
        try:
            return schema.model_validate_json(_strip_fence(text))
        except ValidationError:
            continue
    raise HTTPException(502, "LLM 응답 형식이 올바르지 않습니다.")


def llm_reachable() -> bool:
    try:
        client.models.list(limit=1)
        return True
    except Exception:
        return False
