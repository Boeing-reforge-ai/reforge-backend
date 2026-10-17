"""판정 기준 정리본(단계별 판정 기준 데이터, 판정 기준과 계산법)의 팀 설정값.

구간값·계수는 전부 여기서만 관리한다.
"""

# ── QR ──
QR_VERSION = 1
# lot은 선택 키. 없으면 태그 분실 → 임시 로트(NO_TAG_PREFIX)로 저장하고 노랑 트리거
QR_REQUIRED_KEYS = ("v", "fam", "grade", "temper", "shape", "cert", "kg")
NO_TAG_PREFIX = "NO-TAG-"
# 치수·오염·결함 (LUMP·CONTAM 공통)
QR_CONDITION_KEYS = ("dim", "crack", "foreign", "oil", "dust", "coat", "oxide", "corr", "scratch", "deform", "flags")
# LUMP에서 추가로 필요한 키 (ys·ys_src·quote는 없으면 대표값·PART 값으로 대체)
QR_LUMP_KEYS = ("allow", "chem")
SUPPORTED_FAMS = ("Ti", "Al")
SHAPES = ("LUMP", "CONTAM")  # 칩은 스테이션에 오지 않음

# ── 유형 → 표시명·LED ──
SCRAP_TYPE = {"LUMP": "덩어리형", "CONTAM": "오염형"}
SHAPE_LED = {"LUMP": "G", "CONTAM": "R"}
SCREENING_LED = {"GREEN": "G", "YELLOW": "Y", "RED": "R"}

# ── 소재별 항복강도 대표값 MPa (성적서 없을 때, 출처 D) ──
YS_REF_MPA = {"Ti-6Al-4V": 828, "Ti-Grade2": 276, "Al-7075": 503, "Al-6061": 276}

# ── 밀도 교차검증 ──
DENSITY_TOL = 0.05  # 5% 초과 → 소재 불일치 의심, 노랑 트리거

# ── 오염·결함 경계값 (G = GREEN 상한, Y = YELLOW 상한) ──
THRESHOLDS = {
    "foreign": (0.05, 0.2),  # wt.%
    "oil": (0.2, 1.0),  # wt.%
    "dust": (0.05, 0.25),  # wt.%
    "coat": (5, 30),  # %
    "oxide": (5, 20),  # %
    "corr": (5, 20),  # %
    "scratch": (2, 5),  # 깊이 ÷ 두께 %
    "deform": (2, 5),  # %
}
# 있으면 즉시 RED인 flags
RED_FLAGS = ("foreign_hard", "oil_hard", "deep_pit", "func_surface")
# Y 초과일 때만 RED로 만드는 flags (없으면 제거·교정 가능 → 노랑, 40점)
REMOVABLE_FLAGS = {"coat": "coat_hard", "deform": "straighten_hard"}
SCORE_REMOVABLE = 40

# ── 노랑(추가 확인): 가드밴드 + 항목별 조치 (노랑 판정기준 변경 정리본) ──
# 측정 불확도 w만큼 GREEN 상한 안쪽까지만 초록. G - w < x ≤ Y 이면 노랑
GUARD = {"foreign": 0.01, "oil": 0.05, "dust": 0.01, "coat": 1.0, "oxide": 1.0, "corr": 1.0, "scratch": 0.5, "deform": 1.0}
# 트리거 → 작업자 조치. 같은 조치는 한 번만 표시 (THRESHOLDS 순서 → 그 외 순서로 나열)
YELLOW_ACTION = {
    "foreign": "이종금속 분리 후 XRF 확인",
    "oil": "세척 후 재측정",
    "dust": "세척 후 재측정",
    "coat": "코팅 제거 후 재측정",
    "oxide": "표면 절삭 후 치수 재확인",
    "corr": "표면 절삭 후 치수 재확인",
    "scratch": "표면 절삭 후 치수 재확인",
    "deform": "평탄도 측정",
    "crack": "해당 부위 침투탐상 검사",
    "chem": "성적서 재확인 또는 XRF",
    "density": "소재 재확인 (XRF·성적서 대조)",
    "tag": "XRF로 합금 확인 (로트 없음 → 성적서 필요 후보 불가)",
}
ITEM_NAME = {"foreign": "이종금속", "oil": "오일", "dust": "먼지", "coat": "코팅",
             "oxide": "산화", "corr": "부식", "scratch": "스크래치", "deform": "변형"}
ITEM_UNIT = {"foreign": "wt.%", "oil": "wt.%", "dust": "wt.%"}  # 나머지는 %
# 숫자 아닌 노랑 사유 코드 → (조치 키, 표시 문구)
YELLOW_CODES = {
    "crack_suspected": ("crack", "균열 의심"),
    "chem_border": ("chem", "화학조성 경계"),
    "density_mismatch": ("density", "밀도 불일치"),
    "tag_missing": ("tag", "태그 분실 (로트 미확인)"),
}

# ── 상태 점수 C (화면 표시·우선순위 참고용, 색 판정에는 쓰지 않음) ──
WEIGHTS = {"chem": 0.30, "foreign": 0.20, "surface": 0.15, "oil": 0.10, "coating": 0.10, "struct": 0.15}
CHEM_SCORE = {"IN": 100, "BORDER": 60, "OUT": 0, None: 60}
CRACK_SCORE = {"none": 100, "suspected": 60, "confirmed": 0}
# 색은 트리거로 판정: RED 트리거 → RED, 노랑 트리거 → YELLOW, 둘 다 없으면 GREEN
SCENARIO_SCREENINGS = ("GREEN", "YELLOW")  # 시나리오 생성 가능 (YELLOW는 확인 통과 시 후보)

# ── 우선순위 점수 P ──
P_WEIGHTS = {"material": 35, "geometry": 20, "economics": 25, "demand": 15, "circularity": 5}
D_GRADE_REHEAT = 0.7
STRENGTH_OK_RATIO = 1.5  # r ≤ 1.5 → 1.0
STRENGTH_FLOOR_RATIO = 3.0  # r ≥ 3 → 0.5
STRENGTH_FLOOR = 0.5
D_DATA = {"A": 1.0, "B": 1.0, "C": 0.9, "D": 0.7, "E": 0.6}
SAFETY_CRITICAL_SRC = ("A", "B")
TOP_N = 3

BASELINE = {"name": "신규 소재 구매", "score": 0}
