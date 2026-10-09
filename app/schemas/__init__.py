from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ── 스캔 ──

class ScanCreated(BaseModel):
    scan_id: int
    lot_id: str
    status: str
    led: str


class LatestScan(BaseModel):
    scan_id: int | None
    created_at: datetime | None


class LotOut(BaseModel):
    lot_id: str
    fam: str
    grade: str
    temper: str | None
    cert: bool
    ys: int | None
    ys_src: str | None


class MeasureOut(BaseModel):
    dim_mm: list[float] | None
    kg: float | None
    allow_mm: float | None
    qty: int


class ScanDetail(BaseModel):
    scan_id: int
    status: str
    progress: int
    image_url: str | None
    lot: LotOut
    measure: MeasureOut
    condition: dict[str, Any] | None
    scrap_type: str | None
    led: str | None
    condition_score: float | None
    screening: str | None
    needs_review: bool
    item_scores: dict[str, float] | None
    density_err: float | None
    reason_codes: list[str]
    reusable: bool | None
    error: str | None
    created_at: datetime


# ── 기준 데이터 ──

class PartOut(BaseModel):
    part_id: str
    name: str
    allowed_grades: list[str]
    temper: str | None
    reheat_allowed: bool
    min_dims_mm: list[float]
    min_ys: int
    cert_required: bool
    safety_critical: bool
    part_kg: float | None
    moq: int
    stage: int
    sell_price: int | None
    sell_price_src: str | None
    cost: int


class PlanOut(BaseModel):
    plan_id: int
    part_id: str
    part_name: str
    quantity: int
    due_date: date


# ── 시나리오 ──

class ScenarioGenerateRequest(BaseModel):
    scan_id: int


# ── 제안서 ──

class ProposalGenerateRequest(BaseModel):
    scan_id: int
    scenario_id: int


class SectionsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judgment_basis: str | None = None
    required_docs: str | None = None
    machining_plan: str | None = None
    expected_effect: str | None = None


class ProposalPatch(BaseModel):
    """보낸 필드만 수정. metrics 등 다른 필드는 422"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    summary: str | None = None
    sections: SectionsPatch | None = None
