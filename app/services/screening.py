"""상태 판정 (판정 기준과 계산법 1·2장, 노랑 판정기준 변경 정리본)

빨강 트리거 → 노랑 트리거 → 초록 순서로 색을 정한다. 상태 점수 C는 화면 표시·우선순위 참고용.
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
    GUARD,
    ITEM_NAME,
    ITEM_UNIT,
    RED_FLAGS,
    REMOVABLE_FLAGS,
    SCORE_REMOVABLE,
    SCRAP_TYPE,
    SCREENING_LED,
    THRESHOLDS,
    WEIGHTS,
    YELLOW_ACTION,
    YELLOW_CODES,
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


def judge(
    shape: str, condition: dict[str, Any] | None, dims: tuple | None, kg: float | None, rho_ref: float, tag_missing: bool = False
) -> dict[str, Any]:
    """SCAN에 저장할 판정 결과를 계산한다. DB에 접근하지 않는 순수 함수."""
    c = condition or {}
    flags = set(c.get("flags") or [])
    reasons: list[str] = []
    red = yellow = False

    # 조성·균열: 이탈·확정은 빨강, 경계·의심은 노랑
    chem = c.get("chem")
    if chem == "OUT":
        red = True
        reasons.append("chem_out")
    elif chem == "BORDER":
        yellow = True
        reasons.append("chem_border")

    crack = c.get("crack", "none")
    if crack == "confirmed":
        red = True
        reasons.append("crack_confirmed")
    elif crack == "suspected":
        yellow = True
        reasons.append("crack_suspected")

    for f in RED_FLAGS:
        if f in flags:
            red = True
            reasons.append(f)

    # 항목별: Y 초과 빨강(코팅·변형은 제거·교정 가능하면 노랑), 가드밴드 G - w 초과 노랑
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
                yellow = True
                scores[key] = SCORE_REMOVABLE  # 제거·교정 가능
                reasons.append(f"{key}_over")
        elif x > g - GUARD[key]:
            yellow = True
            reasons.append(f"{key}_warn")

    # 밀도 교차검증
    density = density_err = None
    if dims and kg:
        rho, err = calc_density(dims, kg, rho_ref)
        density, density_err = round(rho, 4), round(err, 4)
        if err > DENSITY_TOL:
            yellow = True
            reasons.append("density_mismatch")

    if tag_missing:
        yellow = True
        reasons.append("tag_missing")

    # 상태 점수 C: 참고용. 빨강은 점수로 상쇄할 수 없어 계산 생략
    score = item_scores = None
    if not red:
        item_scores = {
            "chem": CHEM_SCORE[chem],
            "foreign": scores["foreign"],
            "surface": min(scores["oxide"], scores["corr"], scores["scratch"], scores["dust"]),
            "oil": scores["oil"],
            "coating": scores["coat"],
            "struct": min(CRACK_SCORE[crack], scores["deform"]),
        }
        score = round(sum(WEIGHTS[k] * v for k, v in item_scores.items()), 1)
        item_scores = {k: round(v, 1) for k, v in item_scores.items()}

    if shape == "CONTAM":
        # 오염형은 유형 자체로 재사용 불가
        if not reasons:
            reasons.append("contaminated")
        red = True

    screening = "RED" if red else "YELLOW" if yellow else "GREEN"
    return {
        "scrap_type": SCRAP_TYPE[shape],
        "condition_score": score,
        "screening": screening,
        "needs_review": False,  # 점수 경계 구간(75~85) 폐지. 컬럼만 유지
        "item_scores": item_scores,
        "density": density,
        "density_err": density_err,
        "reason_codes": reasons,
        "reusable": shape == "LUMP" and screening == "GREEN",
        "led": SCREENING_LED[screening],
    }


def yellow_actions(screening: str | None, reason_codes: list[str] | None, condition: dict[str, Any] | None) -> list[dict[str, Any]]:
    """노랑 사유 코드 → 조치별로 묶은 목록 [{action, items}]. 노랑이 아니면 빈 목록"""
    if screening != "YELLOW":
        return []
    codes = set(reason_codes or [])
    c = condition or {}
    groups: dict[str, list[str]] = {}
    for key in THRESHOLDS:
        if f"{key}_warn" in codes or f"{key}_over" in codes:
            unit = ITEM_UNIT.get(key, "%")
            note = {"coat": " (제거 가능)", "deform": " (교정 가능)"}.get(key, "") if f"{key}_over" in codes else ""
            groups.setdefault(YELLOW_ACTION[key], []).append(f"{ITEM_NAME[key]} {c.get(key):g}{unit}{note}")
    for code, (key, label) in YELLOW_CODES.items():
        if code in codes:
            groups.setdefault(YELLOW_ACTION[key], []).append(label)
    return [{"action": action, "items": items} for action, items in groups.items()]


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
            _set_progress(session, scan, 50)  # 빨강·노랑 트리거
            dims = (scan.width_mm, scan.depth_mm, scan.height_mm) if scan.width_mm else None
            tag_missing = not (scan.qr_payload or {}).get("lot")
            result = judge(scan.shape, scan.condition, dims, scan.kg, material.rho_ref, tag_missing)
            _set_progress(session, scan, 80)  # 상태 점수 (참고)
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
