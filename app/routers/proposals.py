from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models import Proposal, Scenario
from app.routers.scans import get_scan_or_404
from app.schemas import ProposalGenerateRequest, ProposalPatch
from app.services import proposal as proposal_service

router = APIRouter(tags=["제안서"])


def get_proposal_or_404(session: Session, proposal_id: int) -> Proposal:
    proposal = session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(404, "제안서를 찾을 수 없습니다.")
    return proposal


@router.post("/proposals/generate", status_code=201)
def generate_proposal(body: ProposalGenerateRequest, session: Session = Depends(get_session)):
    scan = get_scan_or_404(session, body.scan_id)
    scenario = session.get(Scenario, body.scenario_id)
    if scenario is None or scenario.scan_id != scan.id:
        raise HTTPException(404, "시나리오를 찾을 수 없습니다.")
    proposal = proposal_service.generate(session, scan, scenario)
    return proposal_service.to_response(session, proposal)


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: int, session: Session = Depends(get_session)):
    proposal = get_proposal_or_404(session, proposal_id)
    return proposal_service.to_response(session, proposal, with_updated=True)


@router.patch("/proposals/{proposal_id}")
def update_proposal(proposal_id: int, body: ProposalPatch, session: Session = Depends(get_session)):
    proposal = get_proposal_or_404(session, proposal_id)
    changes = body.model_dump(exclude_unset=True, exclude={"sections"})
    if body.sections is not None:
        changes |= body.sections.model_dump(exclude_unset=True)
    for k, v in changes.items():
        if v is not None:
            setattr(proposal, k, v)
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal_service.to_response(session, proposal, with_updated=True)
