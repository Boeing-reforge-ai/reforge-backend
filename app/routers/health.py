from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app.ai.client import llm_reachable
from app.db import get_session

router = APIRouter(tags=["공통"])


@router.get("/health")
def health(session: Session = Depends(get_session)):
    try:
        session.connection().execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    llm_ok = llm_reachable()
    return {
        "status": "ok" if db_ok and llm_ok else "degraded",
        "db_connected": db_ok,
        "llm_api_reachable": llm_ok,
    }
