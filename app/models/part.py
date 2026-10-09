from datetime import date

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


class Part(SQLModel, table=True):
    """후보 제품과 요구조건·가격·비용. 시드 데이터"""

    part_id: str = Field(primary_key=True)  # C-01~
    name: str
    allowed_grades: list[str] = Field(sa_column=Column(ARRAY(Text), nullable=False))
    temper: str | None = None  # 요구 질별, null이면 제한 없음
    reheat_allowed: bool = False  # 질별 불일치 시 재열처리 허용
    min_width_mm: float  # 표면 제거 후 필요 최소 치수 (큰 순서)
    min_depth_mm: float
    min_height_mm: float
    min_ys: int  # 최소 항복강도 MPa
    cert_required: bool = False
    safety_critical: bool = False  # 출처 A·B만 인정
    part_kg: float | None = None  # 완성 부품 질량, null이면 가용 치수 × 기준 밀도 (블랭크)
    moq: int = 1
    stage: int  # 활용 단계 1~6
    sell_price: int | None = None  # 판매가 원, null이면 SCAN.quote 사용
    sell_price_src: str | None = None  # 판매가 출처 등급 A~E
    cost_pre: int = 0  # 전처리비
    cost_proc: int = 0  # 가공비
    cost_insp: int = 0  # 검사비
    cost_log: int = 0  # 물류비


class ProductionPlan(SQLModel, table=True):
    """부품별 생산 예정 수량. 시드 데이터"""

    __tablename__ = "production_plan"

    id: int | None = Field(default=None, primary_key=True)
    part_id: str = Field(foreign_key="part.part_id", index=True)
    quantity: int  # 부품별 합계 = 수요 (d_D)
    due_date: date
