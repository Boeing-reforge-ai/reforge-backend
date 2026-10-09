from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import Part, ProductionPlan
from app.schemas import PartOut, PlanOut

router = APIRouter(tags=["기준 데이터"])


@router.get("/parts", response_model=list[PartOut])
def list_parts(material: str | None = None, session: Session = Depends(get_session)):
    parts = session.exec(select(Part).order_by(Part.part_id)).all()
    if material:
        parts = [p for p in parts if material in p.allowed_grades]
    return [
        PartOut(
            **p.model_dump(include={"part_id", "name", "allowed_grades", "temper", "reheat_allowed", "min_ys", "cert_required",
                                    "safety_critical", "part_kg", "moq", "stage", "sell_price", "sell_price_src"}),
            min_dims_mm=[p.min_width_mm, p.min_depth_mm, p.min_height_mm],
            cost=p.cost_pre + p.cost_proc + p.cost_insp + p.cost_log,
        )
        for p in parts
    ]


@router.get("/production-plans", response_model=list[PlanOut])
def list_plans(weeks: int = Query(3, ge=1), session: Session = Depends(get_session)):
    today = date.today()
    rows = session.exec(
        select(ProductionPlan, Part)
        .join(Part)
        .where(ProductionPlan.due_date >= today, ProductionPlan.due_date <= today + timedelta(weeks=weeks))
        .order_by(ProductionPlan.due_date, ProductionPlan.id)
    ).all()
    return [
        PlanOut(plan_id=plan.id, part_id=part.part_id, part_name=part.name, quantity=plan.quantity, due_date=plan.due_date)
        for plan, part in rows
    ]
