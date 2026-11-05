import hashlib
import json
import logging
from typing import TypeVar

from anthropic import Anthropic, APIConnectionError, APIStatusError, InternalServerError, RateLimitError
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.i18n import tr
from app.models import LlmCache

client = Anthropic(api_key=settings.anthropic_api_key, timeout=60)
log = logging.getLogger(__name__)
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
            log.exception("LLM 연결·한도 오류 (model=%s)", settings.anthropic_model)
            raise HTTPException(503, tr("LLM API에 연결할 수 없습니다.", "Cannot connect to the LLM API."))
        except APIStatusError as e:
            # 모델명 오류(404)·키 오류(401)·잔액 부족(400) 등. 화면에는 뭉뚱그려 보이므로 원인은 로그로 남긴다
            log.error("LLM API 오류 status=%s model=%s body=%s", e.status_code, settings.anthropic_model, e.response.text[:500])
            raise HTTPException(502, tr("LLM 응답 형식이 올바르지 않습니다.", "The LLM response format is invalid."))
        except ValidationError:
            log.warning("LLM 응답이 스키마와 맞지 않아 재시도 (model=%s)", settings.anthropic_model)
            continue
        # 거절·토큰 초과면 스키마를 만족하지 않을 수 있으므로 재시도
        if res.stop_reason in ("refusal", "max_tokens") or res.parsed_output is None:
            log.warning("LLM 응답 사용 불가 stop_reason=%s parsed=%s", res.stop_reason, res.parsed_output is not None)
            continue
        return res.parsed_output
    raise HTTPException(502, tr("LLM 응답 형식이 올바르지 않습니다.", "The LLM response format is invalid."))


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
