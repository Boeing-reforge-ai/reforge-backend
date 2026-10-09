from sqlmodel import Field, SQLModel


class Material(SQLModel, table=True):
    """지원 소재와 기준 밀도. 시드 데이터"""

    name: str = Field(primary_key=True)  # QR grade 값과 동일
    rho_ref: float  # 기준 밀도 g/cm³, 밀도 교차검증용
