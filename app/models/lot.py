from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Lot(SQLModel, table=True):
    """QR의 소재 식별 정보. QR 스캔 시 upsert"""

    lot_id: str = Field(primary_key=True)  # QR lot
    fam: str  # Ti / Al
    grade: str = Field(foreign_key="material.name")  # QR grade
    temper: str | None = None  # annealed / T6
    cert: bool = False  # 성적서 보유
    ys: int | None = None  # 실제 항복강도 MPa
    ys_src: str | None = None  # ys 출처 등급 A~E
    updated_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=_now),
    )
