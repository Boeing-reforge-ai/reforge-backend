import secrets
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.config import settings
from app.core.criteria import SCRAP_TYPE, SHAPE_LED
from app.db import get_session
from app.models import Lot, Material, Scan
from app.models.base import utcnow
from app.schemas import LatestScan, LotOut, MeasureOut, ScanCreated, ScanDetail
from app.services.qr import QrFormatError, UnsupportedMaterialError, lot_fields, parse_qr, scan_fields
from app.services.screening import run_screening

router = APIRouter(tags=["스캔"])

IMAGE_EXTS = (".jpg", ".jpeg", ".png")


def get_scan_or_404(session: Session, scan_id: int) -> Scan:
    scan = session.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(404, "스캔 데이터를 찾을 수 없습니다.")
    return scan


def verify_station(x_station_key: str | None = Header(None)) -> None:
    if not settings.station_key or not x_station_key or not secrets.compare_digest(x_station_key, settings.station_key):
        raise HTTPException(401, "인증되지 않은 스테이션입니다.")


@router.post("/scans", status_code=201, response_model=ScanCreated, dependencies=[Depends(verify_station)])
def create_scan(
    background_tasks: BackgroundTasks,
    qr: str = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    ext = Path(image.filename or "").suffix.lower()
    if ext not in IMAGE_EXTS:
        raise HTTPException(400, "지원하지 않는 이미지 형식입니다.")
    try:
        payload = parse_qr(qr)
    except QrFormatError:
        raise HTTPException(400, "QR 형식이 올바르지 않습니다.")
    except UnsupportedMaterialError:
        raise HTTPException(400, "지원하지 않는 소재입니다.")
    if session.get(Material, payload["grade"]) is None:
        raise HTTPException(400, "지원하지 않는 소재입니다.")

    session.merge(Lot(**lot_fields(payload), updated_at=utcnow()))
    scan = Scan(**scan_fields(payload), scrap_type=SCRAP_TYPE[payload["shape"]], led=SHAPE_LED[payload["shape"]])
    session.add(scan)
    session.flush()

    rel_path = f"scans/{scan.id}{ext}"
    dest = Path(settings.upload_dir) / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(image.file.read())
    scan.image_path = rel_path
    session.commit()

    background_tasks.add_task(run_screening, scan.id)
    return ScanCreated(scan_id=scan.id, lot_id=scan.lot_id, status=scan.status, led=scan.led)


@router.get("/scans/latest", response_model=LatestScan)
def latest_scan(session: Session = Depends(get_session)):
    scan = session.exec(select(Scan).order_by(Scan.id.desc()).limit(1)).first()
    return LatestScan(scan_id=scan.id if scan else None, created_at=scan.created_at if scan else None)


@router.get("/scans/{scan_id}", response_model=ScanDetail)
def get_scan(scan_id: int, session: Session = Depends(get_session)):
    scan = get_scan_or_404(session, scan_id)
    lot = session.get(Lot, scan.lot_id)
    dims = [scan.width_mm, scan.depth_mm, scan.height_mm] if scan.width_mm is not None else None
    done = scan.status == "done"
    return ScanDetail(
        scan_id=scan.id,
        status=scan.status,
        progress=scan.progress,
        image_url=f"/static/{scan.image_path}" if scan.image_path else None,
        lot=LotOut.model_validate(lot, from_attributes=True),
        measure=MeasureOut(dim_mm=dims, kg=scan.kg, allow_mm=scan.allow_mm, qty=scan.qty),
        condition=scan.condition,
        scrap_type=scan.scrap_type,
        led=scan.led,
        condition_score=scan.condition_score,
        screening=scan.screening,
        needs_review=scan.needs_review,
        item_scores=scan.item_scores,
        density_err=scan.density_err,
        reason_codes=scan.reason_codes or [],
        reusable=scan.reusable if done else None,
        error=scan.error,
        created_at=scan.created_at,
    )
