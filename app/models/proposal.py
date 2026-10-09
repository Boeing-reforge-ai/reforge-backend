from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import created_at_column, updated_at_column, utcnow


class Proposal(SQLModel, table=True):
    """선택한 시나리오로 만든 활용 제안서. 수치(metrics)는 저장하지 않고 SCENARIO에서 계산"""

    id: int | None = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="scenario.id", index=True)
    title: str
    summary: str
    judgment_basis: str  # 판정 근거
    required_docs: str  # 필요 서류
    machining_plan: str  # 가공 방향
    expected_effect: str  # 기대효과
    created_at: datetime = Field(default_factory=utcnow, sa_column=created_at_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=updated_at_column())


class LlmCache(SQLModel, table=True):
    """LLM 응답 캐시. 네트워크 장애 시 같은 요청은 캐시로 응답"""

    __tablename__ = "llm_cache"

    id: int | None = Field(default=None, primary_key=True)
    request_hash: str = Field(unique=True, index=True)  # 프롬프트+입력 해시
    task: str  # qualification / proposal
    response: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=created_at_column())
