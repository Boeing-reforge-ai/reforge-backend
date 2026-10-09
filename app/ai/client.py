import hashlib
import json
from typing import TypeVar

from anthropic import Anthropic, APIConnectionError, APIStatusError, InternalServerError, RateLimitError
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, select

from app.core.config import settings
from app.models import LlmCache

client = Anthropic(api_key=settings.anthropic_api_key, timeout=60)
T = TypeVar("T", bound=BaseModel)


def ask_json(system: str, user: str, schema: type[T], retries: int = 1) -> T:
    """LLM에 서술만 맡기고, 응답은 구조화 출력으로 받아 Pydantic 스키마로 검증한다."""
    for _ in range(retries + 1):
        try:
            res = client.messages.parse(
                model=settings.anthropic_model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
        except (APIConnectionError, RateLimitError, InternalServerError):
            raise HTTPException(503, "LLM API에 연결할 수 없습니다.")
        except APIStatusError:
            raise HTTPException(502, "LLM 응답 형식이 올바르지 않습니다.")
        except ValidationError:
            continue
        # 거절·토큰 초과면 스키마를 만족하지 않을 수 있으므로 재시도
        if res.stop_reason in ("refusal", "max_tokens") or res.parsed_output is None:
            continue
        return res.parsed_output
    raise HTTPException(502, "LLM 응답 형식이 올바르지 않습니다.")


def ask_cached(session: Session, task: str, system: str, user: str, schema: type[T]) -> T:
    """같은 요청(모델+프롬프트+입력)은 LLM을 다시 부르지 않고 LLM_CACHE 응답을 쓴다."""
    payload = json.dumps([task, settings.anthropic_model, system, user], ensure_ascii=False)
    request_hash = hashlib.sha256(payload.encode()).hexdigest()
    cached = session.exec(select(LlmCache).where(LlmCache.request_hash == request_hash)).first()
    if cached:
        return schema.model_validate(cached.response)
    result = ask_json(system, user, schema)
    session.add(LlmCache(request_hash=request_hash, task=task, response=result.model_dump()))
    session.commit()
    return result


def llm_reachable() -> bool:
    try:
        client.models.list(limit=1)
        return True
    except Exception:
        return False
