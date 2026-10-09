"""활용 제안서 생성 (LLM). 본문 수치는 LLM이 쓰지 않고 시스템이 metrics를 템플릿에 넣는다."""

import json
from typing import Any

from pydantic import BaseModel
from sqlmodel import Session, select

from app.ai.client import ask_cached
from app.models import Lot, Part, Proposal, Scan, Scenario, ScenarioPart
from app.services.scenario import KNOWLEDGE_BASE, effective_ys

SECTIONS = ("judgment_basis", "required_docs", "machining_plan", "expected_effect")


class ProposalDraft(BaseModel):
    title: str
    summary: str
    judgment_basis: str
    required_docs: str
    machining_plan: str
    expected_effect: str


PROPOSAL_SYSTEM = (
    "당신은 항공 금속 자투리의 재활용 제안서를 쓰는 소재 엔지니어입니다.\n"
    "선정된 시나리오로 제목, 요약, 판정 근거, 필요 서류, 가공 방향, 기대효과를 한국어로 작성하세요.\n"
    "- 절감 질량·절감 금액·소재 활용률 숫자를 직접 쓰지 말고 {saved_kg}, {saved_krw}, {utilization} 자리표시자를 쓰세요. 시스템이 값을 넣습니다.\n"
    "- 그 밖의 수치는 입력에 있는 값만 쓰고, 없는 수치나 사실을 만들지 마세요.\n"
    "- 판정 근거는 실제 LOT 값(등급, 항복강도와 출처, 성적서, 상태 판정)과 부품 요구조건을 연결하세요.\n"
    "- 각 항목은 2~4문장으로 간결하게 쓰세요.\n\n"
    f"도메인 지식 베이스:\n{json.dumps(KNOWLEDGE_BASE, ensure_ascii=False, sort_keys=True)}"
)


def metrics(scan: Scan, scenario: Scenario) -> dict[str, Any]:
    """SCENARIO 값에서 계산 (저장하지 않음, 수정 불가)"""
    return {
        "utilization": round(scenario.d_g, 2),  # 부품 질량 ÷ 자투리 질량
        "reprocess_count": 1,  # 시나리오 1개 = 1회 재가공
        "saved_kg": round(scan.kg * scenario.d_g, 3),  # 신규 소재 대신 쓴 질량
        "saved_krw": scenario.nrv,
    }


def _fill(text: str, m: dict[str, Any]) -> str:
    return (
        text.replace("{saved_kg}", f"{m['saved_kg']:g} kg")
        .replace("{saved_krw}", f"{m['saved_krw']:,}원")
        .replace("{utilization}", f"{m['utilization'] * 100:.0f}%")
    )


def generate(session: Session, scan: Scan, scenario: Scenario) -> Proposal:
    lot = session.get(Lot, scan.lot_id)
    parts = session.exec(select(Part).join(ScenarioPart).where(ScenarioPart.scenario_id == scenario.id)).all()
    ys, ys_src = effective_ys(lot)
    user = json.dumps(
        {
            "lot": {"lot_id": lot.lot_id, "grade": lot.grade, "temper": lot.temper, "cert": lot.cert, "ys_mpa": ys, "ys_src": ys_src},
            "scrap": {
                "dim_mm": [scan.width_mm, scan.depth_mm, scan.height_mm],
                "allow_mm": scan.allow_mm,
                "kg": scan.kg,
                "screening": scan.screening,
                "needs_review": scan.needs_review,
                "reason_codes": scan.reason_codes or [],
            },
            "scenario": {
                "parts": [{"part_id": p.part_id, "name": p.name, "min_ys_mpa": p.min_ys, "cert_required": p.cert_required} for p in parts],
                "usage": scenario.usage,
                "required_docs": scenario.required_docs,
                "reason": scenario.reason,
                "score": scenario.score,
                "rank": scenario.rank,
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    draft = ask_cached(session, "proposal", PROPOSAL_SYSTEM, user, ProposalDraft)
    m = metrics(scan, scenario)
    proposal = Proposal(scenario_id=scenario.id, **{k: _fill(v, m) for k, v in draft.model_dump().items()})
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def to_response(session: Session, proposal: Proposal, with_updated: bool = False) -> dict[str, Any]:
    scenario = session.get(Scenario, proposal.scenario_id)
    scan = session.get(Scan, scenario.scan_id)
    res = {
        "proposal_id": proposal.id,
        "scan_id": scan.id,
        "scenario_id": scenario.id,
        "title": proposal.title,
        "summary": proposal.summary,
        "sections": {k: getattr(proposal, k) for k in SECTIONS},
        "metrics": metrics(scan, scenario),
        "created_at": proposal.created_at,
    }
    if with_updated:
        res["updated_at"] = proposal.updated_at
    return res
