from datetime import datetime

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.models.base import created_at_column, utcnow


class FilterResult(SQLModel, table=True):
    """후보별 형상·자격 필터 통과 여부"""

    __tablename__ = "filter_result"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id", index=True)
    part_id: str = Field(foreign_key="part.part_id")
    filter_type: str  # shape / qualification
    passed: bool
    reason: str | None = None  # 탈락 사유


class Scenario(SQLModel, table=True):
    """재활용 시나리오와 우선순위 점수 P"""

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id", index=True)
    usage: str  # 목업 / EM / 지그 / 보조도구 (LLM)
    required_docs: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(Text), nullable=False))  # LLM
    reason: str  # 용도 판정 근거 (LLM)
    d_m: float  # 소재 적합성 0~1 (35점)
    d_g: float  # 형상·가공 적합성 0~1 (20점)
    d_e: float  # 경제성 0~1 (25점)
    d_d: float  # 시장 수요 0~1 (15점)
    d_r: float  # 순환가치 0~1 (5점)
    nrv: int  # 순회수 가치 원
    score: float  # P 0~100
    rank: int  # 1~3
    is_recommended: bool = False
    created_at: datetime = Field(default_factory=utcnow, sa_column=created_at_column())


class ScenarioPart(SQLModel, table=True):
    """시나리오 ↔ 부품 N:M"""

    __tablename__ = "scenario_part"

    scenario_id: int = Field(foreign_key="scenario.id", primary_key=True)
    part_id: str = Field(foreign_key="part.part_id", primary_key=True)
