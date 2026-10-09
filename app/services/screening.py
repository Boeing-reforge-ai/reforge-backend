"""상태 판정 (판정 기준과 계산법 1·2장)

유형 → 즉시 RED 게이트 → 밀도 교차검증 → 상태 점수 C 순서로 판정한다.
"""

import logging
import time
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.core.criteria import (
    CHEM_SCORE,
    CRACK_SCORE,
    DENSITY_TOL,
    RED_FLAGS,
    REMOVABLE_FLAGS,
    SCORE_GREEN,
    SCORE_REMOVABLE,
    SCORE_REVIEW,
    SCORE_YELLOW,
    SCRAP_TYPE,
    SCREENING_LED,
    SHAPE_LED,
    THRESHOLDS,
    WEIGHTS,
)
from app.db import engine
from app.models import Lot, Material, Scan

log = logging.getLogger(__name__)


def item_score(x: float, g: float, y: float) -> float:
    """측정값 → 항목 점수 (GREEN 100→80, YELLOW 80→40, 초과 0)"""
    if x <= g:
        return 100 - 20 * x / g
    if x <= y:
        return 80 - 40 * (x - g) / (y - g)
    return 0.0


def calc_density(dims: tuple[float, float, float], kg: float, rho_ref: float) -> tuple[float, float]:
    volume_cm3 = dims[0] * dims[1] * dims[2] / 1000
    rho = kg * 1000 / volume_cm3
    return rho, abs(rho - rho_ref) / rho_ref


def judge(shape: str, condition: dict[str, Any] | None, dims: tuple | None, kg: float | None, rho_ref: float) -> dict[str, Any]:
    """SCAN에 저장할 판정 결과를 계산한다. DB에 접근하지 않는 순수 함수."""
    result: dict[str, Any] = {
        "scrap_type": SCRAP_TYPE[shape],
        "condition_score": None,
        "screening": None,
        "needs_review": False,
        "item_scores": None,
        "density": None,
        "density_err": None,
        "reason_codes": [],
        "reusable": False,
        "led": SHAPE_LED[shape],
    }
    if shape == "CHIP":
        return result

    c = condition or {}
    flags = set(c.get("flags") or [])
    reasons: list[str] = []
    red = False

    # 즉시 RED 게이트: 조성 이탈, 확정 균열, RED flags, Y 초과 항목
    chem = c.get("chem")
    if chem == "OUT":
        red = True
        reasons.append("chem_out")
    elif chem == "BORDER":
        reasons.append("chem_border")

    crack = c.get("crack", "none")
    if crack == "confirmed":
        red = True
        reasons.append("crack_confirmed")
    elif crack == "suspected":
        reasons.append("crack_suspected")

    for f in RED_FLAGS:
        if f in flags:
            red = True
            reasons.append(f)

    scores: dict[str, float] = {}
    for key, (g, y) in THRESHOLDS.items():
        x = c.get(key) or 0
        scores[key] = item_score(x, g, y)
        if x > y:
            hard_flag = REMOVABLE_FLAGS.get(key)
            if hard_flag is None:
                red = True
                reasons.append(f"{key}_over")
            elif hard_flag in flags:
                red = True
                reasons.append(hard_flag)
            else:
                scores[key] = SCORE_REMOVABLE  # 제거·교정 가능
                reasons.append(f"{key}_over")
        elif x > g:
            reasons.append(f"{key}_warn")  # YELLOW 구간은 GREEN이어도 기록

    # 밀도 교차검증
    mismatch = False
    if dims and kg:
        rho, err = calc_density(dims, kg, rho_ref)
        result["density"] = round(rho, 4)
        result["density_err"] = round(err, 4)
        if err > DENSITY_TOL:
            mismatch = True
            reasons.append("density_mismatch")

    if red:
        screening = "RED"  # 점수로 상쇄할 수 없는 결함 → 점수 계산 생략
    else:
        item_scores = {
            "chem": CHEM_SCORE[chem],
            "foreign": scores["foreign"],
            "surface": min(scores["oxide"], scores["corr"], scores["scratch"], scores["dust"]),
            "oil": scores["oil"],
            "coating": scores["coat"],
            "struct": min(CRACK_SCORE[crack], scores["deform"]),
        }
        score = round(sum(WEIGHTS[k] * v for k, v in item_scores.items()), 1)
        result["item_scores"] = {k: round(v, 1) for k, v in item_scores.items()}
        result["condition_score"] = score
        if mismatch:
            screening = "YELLOW"
        elif score >= SCORE_GREEN:
            screening = "GREEN"
        elif score >= SCORE_REVIEW:
            screening = "GREEN"
            result["needs_review"] = True
        elif score >= SCORE_YELLOW:
            screening = "YELLOW"
        else:
            screening = "RED"

    if shape == "CONTAM":
        # 오염형은 유형 자체로 재사용 불가
        if not reasons:
            reasons.append("contaminated")
        screening = "RED"

    result["screening"] = screening
    result["reason_codes"] = reasons
    result["reusable"] = shape == "LUMP" and screening == "GREEN"
    result["led"] = SCREENING_LED[screening] if shape == "LUMP" else SHAPE_LED[shape]
    return result


def _set_progress(session: Session, scan: Scan, progress: int) -> None:
    scan.progress = progress
    session.add(scan)
    session.commit()
    time.sleep(settings.analysis_step_sec)


def run_screening(scan_id: int) -> None:
    """백그라운드 상태 판정. 진행률은 SCAN.progress로 폴링한다."""
    with Session(engine) as session:
        scan = session.get(Scan, scan_id)
        if scan is None:
            return
        try:
            _set_progress(session, scan, 20)  # 소재·로트 식별
            lot = session.get(Lot, scan.lot_id)
            material = session.get(Material, lot.grade)
            _set_progress(session, scan, 50)  # 조성·결함 게이트
            dims = (scan.width_mm, scan.depth_mm, scan.height_mm) if scan.width_mm else None
            result = judge(scan.shape, scan.condition, dims, scan.kg, material.rho_ref)
            _set_progress(session, scan, 80)  # 상태 점수
            for k, v in result.items():
                setattr(scan, k, v)
            scan.status = "done"
            scan.progress = 100
        except Exception as e:
            log.exception("scan %s 판정 실패", scan_id)
            session.rollback()
            scan = session.get(Scan, scan_id)
            scan.status = "failed"
            scan.error = str(e) or type(e).__name__
        session.add(scan)
        session.commit()
