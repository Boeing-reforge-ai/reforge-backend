from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from app.core.criteria import SCENARIO_SCREENINGS
from app.db import get_session
from app.models import Scenario
from app.routers.scans import get_scan_or_404
from app.schemas import ScenarioGenerateRequest
from app.services import scenario as scenario_service

router = APIRouter(tags=["시나리오"])


@router.post("/scenarios/generate")
def generate_scenarios(body: ScenarioGenerateRequest, session: Session = Depends(get_session)):
    scan = get_scan_or_404(session, body.scan_id)
    # 초록과 노랑(확인 통과 시 후보)만 시나리오 생성
    if scan.screening not in SCENARIO_SCREENINGS:
        raise HTTPException(409, "재사용 불가 자투리입니다.")
    try:
        return scenario_service.generate(session, scan)
    except scenario_service.NoCandidateError as e:
        return JSONResponse(status_code=422, content={"detail": "조건을 만족하는 후보가 없습니다.", "rejected": e.rejected})


@router.get("/scans/{scan_id}/scenarios")
def list_scenarios(scan_id: int, session: Session = Depends(get_session)):
    scan = get_scan_or_404(session, scan_id)
    if session.exec(select(Scenario.id).where(Scenario.scan_id == scan_id)).first() is None:
        raise HTTPException(404, "생성된 시나리오가 없습니다.")
    return scenario_service.build_response(session, scan)
