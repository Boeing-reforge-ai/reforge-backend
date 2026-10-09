from datetime import datetime
from typing import Any

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.models.base import created_at_column, utcnow


class Scan(SQLModel, table=True):
    """스캔 1건의 QR 원본, 측정·오염 값 스냅샷, 진행 상태, 판정 결과"""

    id: int | None = Field(default=None, primary_key=True)
    lot_id: str = Field(foreign_key="lot.lot_id", index=True)
    qr_payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))  # QR 원본
    image_path: str | None = None  # QR 인식 시 캡처 이미지 경로

    # QR 측정값 스냅샷 (실측 후 QR이 바뀔 수 있어 스캔마다 저장)
    shape: str  # LUMP / CHIP / CONTAM
    width_mm: float | None = None
    depth_mm: float | None = None
    height_mm: float | None = None  # dim, CHIP은 null
    kg: float | None = None
    allow_mm: float | None = None  # 한 면 표면 제거 여유
    qty: int = 1  # 보유 수량
    condition: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))  # chem·crack·foreign~deform·flags
    quote: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))  # {후보ID: [판매가, 비용]}

    # 진행 상태 (상태 판정만 비동기, 웹·스테이션이 폴링)
    status: str = "analyzing"  # analyzing / done / failed
    progress: int = 0  # 0~100
    error: str | None = None  # failed 원인

    # 판정 결과
    scrap_type: str | None = None  # 덩어리형 / 칩형 / 오염형
    condition_score: float | None = None  # 상태 점수 C, CHIP은 null
    screening: str | None = None  # GREEN / YELLOW / RED, CHIP은 null
    needs_review: bool = False  # C 75~85 경계 구간
    item_scores: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))  # chem~struct
    density: float | None = None  # 계산 밀도 g/cm³
    density_err: float | None = None  # 기준 밀도 대비 오차
    reason_codes: list[str] | None = Field(default=None, sa_column=Column(ARRAY(Text)))
    reusable: bool = False  # screening = GREEN만 true
    led: str | None = None  # G / Y / R

    created_at: datetime = Field(default_factory=utcnow, sa_column=created_at_column())
