from sqlmodel import Session

from app.models import Material

# 소재 데이터 문서 기준 대표 밀도 (g/cm³). name은 QR grade 값과 맞춘다
MATERIALS = [
    Material(name="Ti-6Al-4V", rho_ref=4.43),
    Material(name="Ti-Gr2", rho_ref=4.51),
    Material(name="Al-7075", rho_ref=2.81),
    Material(name="Al-6061", rho_ref=2.70),
]


def seed_materials(session: Session) -> None:
    """없는 소재만 추가하고, 있으면 기준 밀도를 시드 값으로 맞춘다."""
    for m in MATERIALS:
        session.merge(m)
    session.commit()
