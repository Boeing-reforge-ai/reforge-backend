from datetime import date, timedelta

from sqlmodel import Session

from app.models import Material, Part, ProductionPlan

# 소재 데이터 문서 기준 대표 밀도 (g/cm³). name은 QR grade 값과 맞춘다 (질별은 QR temper로 따로)
MATERIALS = [
    Material(name="Ti-6Al-4V", rho_ref=4.43),
    Material(name="Ti-Grade2", rho_ref=4.51),
    Material(name="Al-7075", rho_ref=2.81),
    Material(name="Al-6061", rho_ref=2.70),
]

# 단계별 판정 기준 데이터 '제품 후보 DB (Ti)'. 비용은 문서에 합계만 있어 가공비에 넣음
PARTS = [
    Part(
        part_id="C-01", name="조립 치구", allowed_grades=["Ti-6Al-4V"],
        min_width_mm=100, min_depth_mm=60, min_height_mm=25, min_ys=600,
        cert_required=False, part_kg=0.95, moq=1, stage=2,
        sell_price=250_000, cost_proc=70_000,
    ),
    Part(
        part_id="C-02", name="위성 브래킷 목업", allowed_grades=["Ti-6Al-4V"],
        min_width_mm=90, min_depth_mm=50, min_height_mm=20, min_ys=800,
        cert_required=True, part_kg=0.45, moq=1, stage=2,
        sell_price=300_000, cost_proc=115_000,
    ),
    Part(
        # 질량은 가용 치수 × 기준 밀도, 판매가·비용은 QR quote 사용
        part_id="C-03", name="Ti 규격 블랭크", allowed_grades=["Ti-6Al-4V"],
        min_width_mm=60, min_depth_mm=40, min_height_mm=15, min_ys=828,
        cert_required=True, part_kg=None, moq=1, stage=4,
    ),
]

# 부품별 합계가 문서의 수요(C-01 12, C-02 20, C-03 5)와 같도록 나눔. (id, part_id, 수량, 오늘부터 몇 주 뒤)
PLANS = [
    (1, "C-01", 5, 1),
    (2, "C-01", 7, 3),
    (3, "C-02", 12, 2),
    (4, "C-02", 8, 4),
    (5, "C-03", 5, 2),
]


def seed(session: Session) -> None:
    """기준 데이터를 시드 값으로 맞춘다. 서버를 여러 번 켜도 중복되지 않는다."""
    for m in MATERIALS:
        session.merge(m)
    for p in PARTS:
        session.merge(p)
    session.flush()
    # 납기일은 시연 시점 기준으로 항상 앞으로 오도록 시작할 때마다 갱신
    today = date.today()
    for plan_id, part_id, qty, weeks in PLANS:
        session.merge(ProductionPlan(id=plan_id, part_id=part_id, quantity=qty, due_date=today + timedelta(weeks=weeks)))
    session.commit()
