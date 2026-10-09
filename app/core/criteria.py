"""판정 기준 정리본(단계별 판정 기준 데이터, 판정 기준과 계산법)의 팀 설정값.

구간값·계수는 전부 여기서만 관리한다.
"""

# ── QR ──
QR_VERSION = 1
QR_REQUIRED_KEYS = ("v", "lot", "fam", "grade", "temper", "shape", "cert", "kg")
# LUMP·CONTAM에서 필요한 키 (치수·오염·결함)
QR_CONDITION_KEYS = ("dim", "crack", "foreign", "oil", "dust", "coat", "oxide", "corr", "scratch", "deform", "flags")
# LUMP에서 추가로 필요한 키 (ys·ys_src·quote는 없으면 대표값·PART 값으로 대체)
QR_LUMP_KEYS = ("allow", "chem")
SUPPORTED_FAMS = ("Ti", "Al")
SHAPES = ("LUMP", "CHIP", "CONTAM")

# ── 유형 → 표시명·LED ──
SCRAP_TYPE = {"LUMP": "덩어리형", "CHIP": "칩형", "CONTAM": "오염형"}
SHAPE_LED = {"LUMP": "G", "CHIP": "Y", "CONTAM": "R"}
SCREENING_LED = {"GREEN": "G", "YELLOW": "Y", "RED": "R"}

# ── 소재별 항복강도 대표값 MPa (성적서 없을 때, 출처 D) ──
YS_REF_MPA = {"Ti-6Al-4V": 828, "Ti-Grade2": 276, "Al-7075": 503, "Al-6061": 276}

# ── 밀도 교차검증 ──
DENSITY_TOL = 0.05  # 5% 초과 → 소재 불일치 의심, YELLOW

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
# Y 초과일 때만 RED로 만드는 flags (없으면 제거·교정 가능 → 40점)
REMOVABLE_FLAGS = {"coat": "coat_hard", "deform": "straighten_hard"}
SCORE_REMOVABLE = 40

# ── 상태 점수 C ──
WEIGHTS = {"chem": 0.30, "foreign": 0.20, "surface": 0.15, "oil": 0.10, "coating": 0.10, "struct": 0.15}
CHEM_SCORE = {"IN": 100, "BORDER": 60, "OUT": 0, None: 60}
CRACK_SCORE = {"none": 100, "suspected": 60, "confirmed": 0}
SCORE_GREEN = 85
SCORE_REVIEW = 75  # 75~85: GREEN + 검토 필요
SCORE_YELLOW = 40

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
