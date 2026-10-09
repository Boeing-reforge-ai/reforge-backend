"""시나리오 생성 (판정 기준과 계산법 3·4장)

형상 필터 → 자격 필터 → 우선순위 점수 P → 상위 3개 용도 판정(LLM) 순서로 실행한다.
점수와 통과·탈락은 전부 시스템이 계산하고, LLM은 usage·required_docs·reason만 쓴다.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import Session, col, delete, select

from app.ai.client import ask_cached
from app.core.criteria import (
    BASELINE,
    D_DATA,
    D_GRADE_REHEAT,
    P_WEIGHTS,
    SAFETY_CRITICAL_SRC,
    STRENGTH_FLOOR,
    STRENGTH_FLOOR_RATIO,
    STRENGTH_OK_RATIO,
    TOP_N,
    YS_REF_MPA,
)
from app.models import FilterResult, Lot, Material, Part, ProductionPlan, Proposal, Scan, Scenario, ScenarioPart

KNOWLEDGE_BASE = json.loads((Path(__file__).parent.parent / "data" / "knowledge_base.json").read_text())


class NoCandidateError(Exception):
    """형상·자격 필터 통과 후보 0개 (422)"""

    def __init__(self, rejected: list[dict[str, Any]]):
        self.rejected = rejected


@dataclass
class Evaluation:
    part: Part
    passed: bool = True
    filter_type: str | None = None  # 탈락한 필터
    reason: str | None = None
    axes: dict[str, float] = field(default_factory=dict)  # d_m, d_g, d_e, d_d, d_r
    nrv: int = 0
    score: float = 0.0


# ── 계산 ──

def usable_dims(scan: Scan) -> list[float]:
    """표면 제거 여유를 뺀 가용 치수, 큰 순서"""
    a = scan.allow_mm or 0
    return sorted((d - 2 * a for d in (scan.width_mm, scan.depth_mm, scan.height_mm)), reverse=True)


def effective_ys(lot: Lot) -> tuple[int, str]:
    """실제 항복강도와 출처. 없으면 소재 대표값(출처 D)"""
    if lot.ys:
        return lot.ys, lot.ys_src or "E"
    return YS_REF_MPA[lot.grade], "D"


def economics(scan: Scan, part: Part) -> tuple[int, int]:
    """(판매가, 비용). SCAN.quote에 견적이 있으면 우선"""
    quote = (scan.quote or {}).get(part.part_id)
    if quote:
        return int(quote[0]), int(quote[1])
    cost = part.cost_pre + part.cost_proc + part.cost_insp + part.cost_log
    return part.sell_price or 0, cost


def shape_filter(usable: list[float], part: Part) -> str | None:
    mins = sorted((part.min_width_mm, part.min_depth_mm, part.min_height_mm), reverse=True)
    if any(u < m for u, m in zip(usable, mins)):
        fmt = lambda xs: "×".join(f"{x:g}" for x in xs)  # noqa: E731
        return f"가용 치수 {fmt(usable)} mm가 최소 {fmt(mins)} mm보다 작음"
    return None


def qualification_filter(lot: Lot, part: Part, ys: int, ys_src: str) -> str | None:
    reasons = []
    if lot.grade not in part.allowed_grades:
        reasons.append(f"소재 {lot.grade} 미허용 (허용: {', '.join(part.allowed_grades)})")
    if part.temper and lot.temper != part.temper and not part.reheat_allowed:
        reasons.append(f"질별 {lot.temper} ≠ 요구 {part.temper}")
    if ys < part.min_ys:
        reasons.append(f"항복강도 {ys} MPa < 요구 {part.min_ys} MPa")
    if part.cert_required and not lot.cert:
        reasons.append("성적서 필수 부품")
    if part.safety_critical and ys_src not in SAFETY_CRITICAL_SRC:
        reasons.append(f"안전 핵심 부품은 실측·성적서 강도만 인정 (현재 출처 {ys_src})")
    return "; ".join(reasons) or None


def d_strength(r: float) -> float:
    if r <= STRENGTH_OK_RATIO:
        return 1.0
    if r >= STRENGTH_FLOOR_RATIO:
        return STRENGTH_FLOOR
    return 1 - (1 - STRENGTH_FLOOR) * (r - STRENGTH_OK_RATIO) / (STRENGTH_FLOOR_RATIO - STRENGTH_OK_RATIO)


def score_axes(scan: Scan, lot: Lot, part: Part, rho_ref: float, demand: int, max_demand: int, ys: int, ys_src: str) -> tuple[dict[str, float], int]:
    d_grade = 1.0 if not part.temper or lot.temper == part.temper else D_GRADE_REHEAT
    d_m = d_grade * d_strength(ys / part.min_ys) * D_DATA[ys_src]

    part_kg = part.part_kg
    if part_kg is None:  # 블랭크: 가용 치수 그대로 판매
        u = usable_dims(scan)
        part_kg = u[0] * u[1] * u[2] / 1000 * rho_ref / 1000
    d_g = min(1.0, part_kg / scan.kg)

    price, cost = economics(scan, part)
    nrv = price - cost
    d_e = min(1.0, max(0.0, nrv / price)) if price else 0.0

    d_d = (demand / max_demand if max_demand else 0.0) * min(1.0, scan.qty / part.moq)
    d_r = (6 - part.stage) / 5
    return {"d_m": d_m, "d_g": d_g, "d_e": d_e, "d_d": d_d, "d_r": d_r}, nrv


def total_score(axes: dict[str, float]) -> float:
    return (
        P_WEIGHTS["material"] * axes["d_m"]
        + P_WEIGHTS["geometry"] * axes["d_g"]
        + P_WEIGHTS["economics"] * axes["d_e"]
        + P_WEIGHTS["demand"] * axes["d_d"]
        + P_WEIGHTS["circularity"] * axes["d_r"]
    )


def demand_by_part(session: Session) -> dict[str, int]:
    totals: dict[str, int] = {}
    for plan in session.exec(select(ProductionPlan)):
        totals[plan.part_id] = totals.get(plan.part_id, 0) + plan.quantity
    return totals


def evaluate(session: Session, scan: Scan, lot: Lot) -> list[Evaluation]:
    material = session.get(Material, lot.grade)
    parts = session.exec(select(Part).order_by(Part.part_id)).all()
    demand = demand_by_part(session)
    # 수요 분모는 통과 후보가 아니라 같은 소재 계열 후보 DB 전체의 최대값
    same_fam = [p for p in parts if any(g.startswith(f"{lot.fam}-") for g in p.allowed_grades)]
    max_demand = max((demand.get(p.part_id, 0) for p in same_fam), default=0)
    ys, ys_src = effective_ys(lot)
    usable = usable_dims(scan)

    results = []
    for part in parts:
        ev = Evaluation(part=part)
        if reason := shape_filter(usable, part):
            ev.passed, ev.filter_type, ev.reason = False, "shape", reason
        elif reason := qualification_filter(lot, part, ys, ys_src):
            ev.passed, ev.filter_type, ev.reason = False, "qualification", reason
        else:
            ev.axes, ev.nrv = score_axes(scan, lot, part, material.rho_ref, demand.get(part.part_id, 0), max_demand, ys, ys_src)
            ev.score = round(total_score(ev.axes), 1)
        results.append(ev)
    return results


# ── LLM 용도 판정 ──

class UsageJudgment(BaseModel):
    part_id: str
    usage: Literal["목업", "EM", "지그", "보조도구"]
    required_docs: list[str]
    reason: str


class UsageJudgments(BaseModel):
    items: list[UsageJudgment]


USAGE_SYSTEM = (
    "당신은 항공 금속 자투리의 재활용 용도를 판정하는 소재 엔지니어입니다.\n"
    "후보 부품마다 용도(usage), 필요 서류(required_docs), 판정 근거(reason)를 한국어로 작성하세요.\n"
    "- 후보 통과·탈락과 점수는 이미 시스템이 계산했으니 다시 판단하지 마세요.\n"
    "- reason은 1~2문장으로, 입력에 있는 실제 LOT 값(등급, 항복강도와 출처, 성적서, 상태)과 부품 요구조건을 연결하세요.\n"
    "- 입력에 없는 수치나 사실을 만들지 마세요.\n"
    "- required_docs는 지식 베이스의 required_docs_catalog 항목 이름을 그대로 쓰세요.\n"
    "- 입력의 모든 후보에 대해 part_id를 그대로 써서 하나씩 답하세요.\n\n"
    f"도메인 지식 베이스:\n{json.dumps(KNOWLEDGE_BASE, ensure_ascii=False, sort_keys=True)}"
)


def judge_usage(session: Session, scan: Scan, lot: Lot, evs: list[Evaluation]) -> dict[str, UsageJudgment]:
    ys, ys_src = effective_ys(lot)
    user = json.dumps(
        {
            "lot": {"lot_id": lot.lot_id, "grade": lot.grade, "temper": lot.temper, "cert": lot.cert, "ys_mpa": ys, "ys_src": ys_src},
            "scrap": {
                "dim_mm": [scan.width_mm, scan.depth_mm, scan.height_mm],
                "kg": scan.kg,
                "screening": scan.screening,
                "needs_review": scan.needs_review,
                "reason_codes": scan.reason_codes or [],
                "condition": scan.condition,
            },
            "candidates": [
                {
                    "part_id": ev.part.part_id,
                    "name": ev.part.name,
                    "min_ys_mpa": ev.part.min_ys,
                    "cert_required": ev.part.cert_required,
                    "safety_critical": ev.part.safety_critical,
                    "stage": ev.part.stage,
                }
                for ev in evs
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    result = ask_cached(session, "qualification", USAGE_SYSTEM, user, UsageJudgments)
    by_part = {j.part_id: j for j in result.items}
    if any(ev.part.part_id not in by_part for ev in evs):
        raise HTTPException(502, "LLM 응답 형식이 올바르지 않습니다.")
    return by_part


# ── 저장·조회 ──

def clear_scenarios(session: Session, scan_id: int) -> None:
    """같은 스캔으로 다시 만들면 기존 결과를 지우고 새로 저장"""
    scenario_ids = session.exec(select(Scenario.id).where(Scenario.scan_id == scan_id)).all()
    if scenario_ids:
        session.exec(delete(Proposal).where(col(Proposal.scenario_id).in_(scenario_ids)))
        session.exec(delete(ScenarioPart).where(col(ScenarioPart.scenario_id).in_(scenario_ids)))
        session.exec(delete(Scenario).where(col(Scenario.id).in_(scenario_ids)))
    session.exec(delete(FilterResult).where(FilterResult.scan_id == scan_id))


def generate(session: Session, scan: Scan) -> dict[str, Any]:
    lot = session.get(Lot, scan.lot_id)
    evs = evaluate(session, scan, lot)
    passed = sorted((ev for ev in evs if ev.passed), key=lambda ev: ev.score, reverse=True)[:TOP_N]
    # LLM은 저장 전에 호출해, 실패하면 기존 결과를 그대로 둔다
    usages = judge_usage(session, scan, lot, passed) if passed else {}

    clear_scenarios(session, scan.id)
    for ev in evs:
        session.add(FilterResult(scan_id=scan.id, part_id=ev.part.part_id, filter_type="shape", passed=ev.filter_type != "shape",
                                 reason=ev.reason if ev.filter_type == "shape" else None))
        if ev.filter_type != "shape":
            session.add(FilterResult(scan_id=scan.id, part_id=ev.part.part_id, filter_type="qualification", passed=ev.passed,
                                     reason=ev.reason if ev.filter_type == "qualification" else None))
    if not passed:
        session.commit()
        raise NoCandidateError(rejected_list(session, scan.id))

    for rank, ev in enumerate(passed, start=1):
        u = usages[ev.part.part_id]
        scenario = Scenario(
            scan_id=scan.id, usage=u.usage, required_docs=u.required_docs, reason=u.reason,
            **{k: round(v, 4) for k, v in ev.axes.items()},
            nrv=ev.nrv, score=ev.score, rank=rank, is_recommended=rank == 1,
        )
        session.add(scenario)
        session.flush()
        session.add(ScenarioPart(scenario_id=scenario.id, part_id=ev.part.part_id))
    session.commit()
    return build_response(session, scan)


def rejected_list(session: Session, scan_id: int) -> list[dict[str, Any]]:
    rows = session.exec(
        select(FilterResult, Part).join(Part).where(FilterResult.scan_id == scan_id, FilterResult.passed == False).order_by(FilterResult.part_id)  # noqa: E712
    ).all()
    return [{"part_id": p.part_id, "name": p.name, "filter_type": fr.filter_type, "reason": fr.reason} for fr, p in rows]


def build_response(session: Session, scan: Scan) -> dict[str, Any]:
    """POST /scenarios/generate와 GET /scans/{id}/scenarios 공통 응답"""
    rejected = rejected_list(session, scan.id)
    rejected_ids = {r["part_id"] for r in rejected}
    checked = session.exec(
        select(Part).join(FilterResult).where(FilterResult.scan_id == scan.id).distinct().order_by(Part.part_id)
    ).all()
    candidates = [{"part_id": p.part_id, "name": p.name} for p in checked if p.part_id not in rejected_ids]

    scenarios = []
    recommended_id = None
    for s in session.exec(select(Scenario).where(Scenario.scan_id == scan.id).order_by(Scenario.rank)):
        parts = session.exec(select(Part).join(ScenarioPart).where(ScenarioPart.scenario_id == s.id).order_by(Part.part_id)).all()
        sell_price = sum(economics(scan, p)[0] for p in parts)
        if s.is_recommended:
            recommended_id = s.id
        scenarios.append({
            "scenario_id": s.id,
            "rank": s.rank,
            "parts": [{"part_id": p.part_id, "name": p.name} for p in parts],
            "usage": s.usage,
            "required_docs": s.required_docs,
            "reason": s.reason,
            "breakdown": {
                "material": round(P_WEIGHTS["material"] * s.d_m, 1),
                "geometry": round(P_WEIGHTS["geometry"] * s.d_g, 1),
                "economics": round(P_WEIGHTS["economics"] * s.d_e, 1),
                "demand": round(P_WEIGHTS["demand"] * s.d_d, 1),
                "circularity": round(P_WEIGHTS["circularity"] * s.d_r, 1),
            },
            "nrv": s.nrv,
            "sell_price": sell_price,
            "score": s.score,
        })
    return {"candidates": candidates, "rejected": rejected, "scenarios": scenarios, "baseline": BASELINE, "recommended_id": recommended_id}
