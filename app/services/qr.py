"""QR JSON 검증과 SCAN 스냅샷 변환 (QR 데이터 정리본 키 사전 기준)"""

import json
from typing import Any

from app.core.criteria import (
    CHEM_SCORE,
    CRACK_SCORE,
    QR_CONDITION_KEYS,
    QR_LUMP_KEYS,
    QR_REQUIRED_KEYS,
    QR_VERSION,
    SHAPES,
    SUPPORTED_FAMS,
    THRESHOLDS,
)

CONDITION_FIELDS = ("chem", "crack", *THRESHOLDS, "flags")


class QrFormatError(ValueError):
    """QR 형식 오류 (400 "QR 형식이 올바르지 않습니다.")"""


class UnsupportedMaterialError(ValueError):
    """지원하지 않는 소재 (400 "지원하지 않는 소재입니다.")"""


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def parse_qr(raw: str) -> dict[str, Any]:
    try:
        qr = json.loads(raw)
    except json.JSONDecodeError as e:
        raise QrFormatError("JSON 파싱 실패") from e
    if not isinstance(qr, dict):
        raise QrFormatError("JSON 객체가 아님")

    shape = qr.get("shape")
    required = list(QR_REQUIRED_KEYS)
    if shape in ("LUMP", "CONTAM"):
        required += QR_CONDITION_KEYS
    if shape == "LUMP":
        required += QR_LUMP_KEYS
    missing = [k for k in required if k not in qr]
    if missing:
        raise QrFormatError(f"필수 키 누락: {', '.join(missing)}")

    if qr["v"] != QR_VERSION:
        raise QrFormatError(f"지원하지 않는 버전: {qr['v']}")
    if shape not in SHAPES:
        raise QrFormatError(f"shape 값 오류: {shape}")
    if qr["fam"] not in SUPPORTED_FAMS:
        raise UnsupportedMaterialError(qr["fam"])
    for k in ("lot", "grade", "temper"):
        if not isinstance(qr[k], str) or not qr[k]:
            raise QrFormatError(f"{k} 값 오류")
    if qr["cert"] not in (0, 1):
        raise QrFormatError("cert 값 오류")
    if not _is_number(qr["kg"]) or qr["kg"] <= 0:
        raise QrFormatError("kg 값 오류")

    if "dim" in qr:
        dim = qr["dim"]
        if not (isinstance(dim, list) and len(dim) == 3 and all(_is_number(d) and d > 0 for d in dim)):
            raise QrFormatError("dim 값 오류")
    if "allow" in qr and (not _is_number(qr["allow"]) or qr["allow"] < 0):
        raise QrFormatError("allow 값 오류")
    if "chem" in qr and qr["chem"] not in CHEM_SCORE:
        raise QrFormatError("chem 값 오류")
    if "crack" in qr and qr["crack"] not in CRACK_SCORE:
        raise QrFormatError("crack 값 오류")
    for k in THRESHOLDS:
        if k in qr and (not _is_number(qr[k]) or qr[k] < 0):
            raise QrFormatError(f"{k} 값 오류")
    if "flags" in qr and not (isinstance(qr["flags"], list) and all(isinstance(f, str) for f in qr["flags"])):
        raise QrFormatError("flags 값 오류")
    if "ys" in qr and (not _is_number(qr["ys"]) or qr["ys"] <= 0):
        raise QrFormatError("ys 값 오류")
    if "ys_src" in qr and qr["ys_src"] not in ("A", "B", "C", "D", "E"):
        raise QrFormatError("ys_src 값 오류")
    if "qty" in qr and (not isinstance(qr["qty"], int) or qr["qty"] < 1):
        raise QrFormatError("qty 값 오류")
    if "quote" in qr:
        quote = qr["quote"]
        if not isinstance(quote, dict) or not all(
            isinstance(v, list) and len(v) == 2 and all(_is_number(n) for n in v) for v in quote.values()
        ):
            raise QrFormatError("quote 값 오류")
    return qr


def lot_fields(qr: dict[str, Any]) -> dict[str, Any]:
    return {
        "lot_id": qr["lot"],
        "fam": qr["fam"],
        "grade": qr["grade"],
        "temper": qr["temper"],
        "cert": bool(qr["cert"]),
        "ys": qr.get("ys"),
        "ys_src": qr.get("ys_src"),
    }


def scan_fields(qr: dict[str, Any]) -> dict[str, Any]:
    """QR에 없는 키는 null로 저장 (0으로 채우지 않음)"""
    width, depth, height = qr.get("dim") or (None, None, None)
    condition = None
    if qr["shape"] != "CHIP":
        condition = {k: qr.get(k) for k in CONDITION_FIELDS}
    return {
        "lot_id": qr["lot"],
        "qr_payload": qr,
        "shape": qr["shape"],
        "width_mm": width,
        "depth_mm": depth,
        "height_mm": height,
        "kg": qr["kg"],
        "allow_mm": qr.get("allow"),
        "qty": qr.get("qty", 1),
        "condition": condition,
        "quote": qr.get("quote"),
    }
