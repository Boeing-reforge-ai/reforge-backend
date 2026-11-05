"""언어(ko/en) 처리. 응답 문구와 LLM 생성 언어를 고른다.

현재는 영어 전용이다. set_lang이 요청 헤더와 상관없이 항상 en으로 고정한다.
한국어를 다시 켜려면 set_lang에서 ?lang=ko 또는 Accept-Language를 읽어 _lang에 넣으면 된다.
(한국어 문구·프롬프트는 코드에 그대로 남아 있다)
서비스 코드는 current_lang()/tr()/L()로 꺼내 쓴다.
"""

from contextvars import ContextVar
from typing import Literal

Lang = Literal["ko", "en"]
DEFAULT_LANG: Lang = "en"
_lang: ContextVar[Lang] = ContextVar("lang", default=DEFAULT_LANG)


def current_lang() -> Lang:
    return _lang.get()


def tr(ko: str, en: str) -> str:
    return en if current_lang() == "en" else ko


# async여야 같은 컨텍스트에 값이 저장되어 뒤이어 실행되는 동기 엔드포인트에서 보인다
async def set_lang() -> None:
    _lang.set(DEFAULT_LANG)


# DB·상수에는 한국어 원문을 두고, 영어 요청일 때만 표시 시점에 바꾼다 (키 = 한국어 원문)
EN_TEXT: dict[str, str] = {
    # 노랑 조치
    "이종금속 분리 후 XRF 확인": "Separate foreign metal, then verify with XRF",
    "세척 후 재측정": "Re-measure after cleaning",
    "코팅 제거 후 재측정": "Re-measure after removing coating",
    "표면 절삭 후 치수 재확인": "Re-check dimensions after surface cutting",
    "평탄도 측정": "Measure flatness",
    "해당 부위 침투탐상 검사": "Dye-penetrant inspection of the affected area",
    "성적서 재확인 또는 XRF": "Re-check certificate or XRF",
    "소재 재확인 (XRF·성적서 대조)": "Re-verify material (XRF / certificate cross-check)",
    "XRF로 합금 확인 (로트 없음 → 성적서 필요 후보 불가)": "Verify alloy by XRF (no lot → candidates requiring a certificate not possible)",
    # 항목명·사유
    "이종금속": "Foreign metal", "오일": "Oil", "먼지": "Dust", "코팅": "Coating",
    "산화": "Oxidation", "부식": "Corrosion", "스크래치": "Scratch", "변형": "Deformation",
    " (제거 가능)": " (removable)", " (교정 가능)": " (straightenable)",
    "균열 의심": "Crack suspected", "화학조성 경계": "Composition borderline",
    "밀도 불일치": "Density mismatch", "태그 분실 (로트 미확인)": "Tag missing (lot unverified)",
    # 부품명
    "조립 치구": "Assembly Fixture", "위성 브래킷 목업": "Satellite Bracket Mock-up", "Ti 규격 블랭크": "Ti Standard Blank",
    # 필요 서류 카탈로그
    "원본 재질증명서 (LOT 성적서)": "Original mill certificate (lot certificate)",
    "치수 검사 성적서": "Dimensional inspection report",
    "LOT 추적 기록 (원본 로트 → 절단 파생 ID)": "Lot traceability record (original lot → derived cut ID)",
    "열처리 이력": "Heat-treatment history",
    "비파괴검사 결과": "Non-destructive testing results",
    "표면 세척·전처리 기록": "Surface cleaning / pre-treatment record",
    # 기타
    "신규 소재 구매": "Buy new material",
}


def L(text: str) -> str:
    """한국어 원문을 현재 요청 언어로. 번역표에 없으면 그대로"""
    return EN_TEXT.get(text, text) if current_lang() == "en" else text
