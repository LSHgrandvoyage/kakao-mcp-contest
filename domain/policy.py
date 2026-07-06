"""위험 판정 도메인 로직 (순수 함수 — DB·외부 API 무관, 단위 테스트 대상).

제품 원칙(spec §6) 강제:
- "안전하다" 판정 절대 금지. 역할은 **위험 신호 탐지 + 확인 항목 안내**.
- 신뢰도(표본수)를 항상 함께 반환. 빌라는 시세 신뢰도가 낮음을 구조적으로 반영.
- 진단성 출력엔 면책 포함.

임계값은 하드코딩이 아니라 이 모듈 상단 상수로 분리한다(brief §7 OCP).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ── 정책 상수 (설정 분리) ─────────────────────────────
# 전세가율(%) 위험 신호 구간. 관례(깡통전세 통용 80%) 기반, 조정 가능.
RATIO_HIGH_SIGNAL = 80.0   # 이상: 고위험 신호
RATIO_CAUTION = 70.0       # 이상 80 미만: 주의
# 미만 70: 위험 신호 낮음 (그래도 "안전"이라 하지 않음)

# 신뢰도 등급 표본수 경계
SAMPLE_HIGH = 5            # 이상: 높음
SAMPLE_MEDIUM = 3         # 이상 5 미만: 보통
SAMPLE_LOW = 1            # 이상 3 미만: 낮음
# 0 또는 시세 없음: 없음

# 전세보증보험(HUG) 가입 가능성 추정 경계 — 부채비율 (선순위+보증금)÷시세(%)
GUARANTEE_LIKELY_MAX = 80.0       # 이하: 가능성 높음
GUARANTEE_BORDERLINE_MAX = 100.0  # 이하: 경계(조건 확인)
SENIOR_DEBT_GATE = 60.0           # 선순위 근저당이 시세의 이 %를 넘으면 거절 가능성

DISCLAIMER = "참고용 1차 스크리닝입니다. 법률 자문이 아니며, 계약 전 공인중개사·등기부로 직접 확인하세요."


class Confidence(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskZone(str, Enum):
    UNKNOWN = "unknown"        # 시세 산정 불가
    LOW_SIGNAL = "low_signal"  # 위험 신호 낮음(≠안전)
    CAUTION = "caution"
    HIGH_SIGNAL = "high_signal"


class Guarantee(str, Enum):
    UNKNOWN = "unknown"        # 시세 없음 → 추정 불가
    LIKELY = "likely"          # 가입 가능성 높음
    BORDERLINE = "borderline"  # 경계(조건 확인 필요)
    UNLIKELY = "unlikely"      # 거절 가능성 있음


@dataclass
class GuaranteeEstimate:
    level: Guarantee
    note: str


@dataclass
class RiskAssessment:
    jeonse_ratio: float | None          # 전세가율(%) = 보증금÷시세, 시세 없으면 None
    zone: RiskZone
    confidence: Confidence
    sample_count: int
    median_price: int | None            # 매매 시세 중앙값(원)
    secured_ratio: float | None = None  # 회수부담률(%) = (선순위+보증금)÷시세, 근저당 입력 시만
    senior_debt: int = 0                # 반영된 선순위 채권최고액(원)
    senior_deposit: int = 0             # 반영된 선순위 임차보증금(원)
    guarantee: GuaranteeEstimate | None = None  # 전세보증보험(HUG) 가입 가능성 추정
    signals: list[str] = field(default_factory=list)   # 위험 신호(신호 언어)
    verify_items: list[str] = field(default_factory=list)  # 사용자가 직접 확인할 항목
    disclaimer: str = DISCLAIMER


# 어떤 경우에도 사용자가 직접 확인해야 하는 항목(우리가 판정하지 않는 영역)
# 근거: 주택임대차보호법 제3조, 국세청 미납국세 열람 제도(2023.4.3 시행)
_BASE_VERIFY = [
    "등기부등본 을구에서 근저당·가압류·신탁등기 등 선순위 권리 확인",
    "임대인 미납국세 열람(보증금 1천만원 초과 시 임대인 동의 없이, 계약 후 임대차 시작일까지 전국 세무서에서 가능)",
    "잔금·입주일에 전입신고+확정일자 처리(대항력은 전입신고 다음 날 0시, 우선변제권은 확정일자로 발생)",
]


def classify_confidence(sample_count: int, property_type: str) -> Confidence:
    if sample_count <= 0:
        return Confidence.NONE
    if sample_count >= SAMPLE_HIGH:
        level = Confidence.HIGH
    elif sample_count >= SAMPLE_MEDIUM:
        level = Confidence.MEDIUM
    else:
        level = Confidence.LOW
    # 빌라는 비교 실거래가 희소 → 신뢰도 한 등급 하향(최대 보통)
    if property_type == "villa" and level == Confidence.HIGH:
        level = Confidence.MEDIUM
    return level


def classify_zone(ratio: float) -> RiskZone:
    if ratio >= RATIO_HIGH_SIGNAL:
        return RiskZone.HIGH_SIGNAL
    if ratio >= RATIO_CAUTION:
        return RiskZone.CAUTION
    return RiskZone.LOW_SIGNAL


def estimate_guarantee(deposit: int, median_price: int, senior_debt: int,
                       senior_deposit: int) -> GuaranteeEstimate:
    """전세보증보험(HUG) 가입 가능성 추정 — 부채비율 (선순위+보증금)÷시세 기반 근사치.

    실제 HUG 심사는 시세가 아닌 공시가격 기준이라, 이 추정은 낙관적일 수 있음을 note로 고지한다.
    """
    senior_total = (senior_debt or 0) + (senior_deposit or 0)
    burden = 100.0 * (senior_total + deposit) / median_price

    if 100.0 * (senior_debt or 0) / median_price > SENIOR_DEBT_GATE:
        level = Guarantee.UNLIKELY  # 선순위 근저당 과다
    elif burden > GUARANTEE_BORDERLINE_MAX:
        level = Guarantee.UNLIKELY
    elif burden > GUARANTEE_LIKELY_MAX:
        level = Guarantee.BORDERLINE
    else:
        level = Guarantee.LIKELY

    note = "HUG는 시세가 아닌 공시가격 기준으로 심사하므로 실제 기준은 더 엄격할 수 있는 추정치입니다."
    if senior_total == 0:
        note += " (선순위 채권 미반영 — 근저당이 있으면 가능성이 더 낮아집니다.)"
    return GuaranteeEstimate(level, note)


def assess(deposit: int, median_price: int | None, sample_count: int,
           property_type: str, senior_debt: int = 0, senior_deposit: int = 0) -> RiskAssessment:
    """전세 보증금 + 사전집계 시세(+ 선택: 등기부 선순위) → 위험 평가. 순수 함수.

    senior_debt(근저당 채권최고액)·senior_deposit(다가구 선순위 보증금)이 주어지면
    회수부담률 = (선순위 + 보증금) ÷ 시세 를 계산해 위험구간을 그 기준으로 판정한다.
    """
    verify = list(_BASE_VERIFY)

    # 시세를 못 구한 경우: 판정하지 않고 확인을 안내(에러 아님, 제품 원칙)
    if not median_price or sample_count <= 0:
        return RiskAssessment(
            jeonse_ratio=None, zone=RiskZone.UNKNOWN, confidence=Confidence.NONE,
            sample_count=sample_count, median_price=median_price,
            senior_debt=senior_debt or 0, senior_deposit=senior_deposit or 0,
            guarantee=GuaranteeEstimate(Guarantee.UNKNOWN,
                "시세를 산정할 수 없어 보증보험 가입 가능성도 추정할 수 없습니다."),
            signals=["최근 실거래 기준 시세를 산정할 만한 비교 거래가 부족합니다(시세 신뢰도 없음)."],
            verify_items=verify,
        )

    jeonse_ratio = round(100.0 * deposit / median_price, 1)
    senior_total = (senior_debt or 0) + (senior_deposit or 0)
    secured_ratio = (round(100.0 * (senior_total + deposit) / median_price, 1)
                     if senior_total > 0 else None)
    ratio_for_zone = secured_ratio if secured_ratio is not None else jeonse_ratio

    zone = classify_zone(ratio_for_zone)
    confidence = classify_confidence(sample_count, property_type)

    label = "회수부담률" if secured_ratio is not None else "전세가율"
    signals: list[str] = []
    if zone == RiskZone.HIGH_SIGNAL:
        signals.append(f"{label}이 {ratio_for_zone}%로 고위험 신호 구간입니다(깡통전세 위험 주의).")
    elif zone == RiskZone.CAUTION:
        signals.append(f"{label}이 {ratio_for_zone}%로 주의 구간입니다.")
    else:
        signals.append(f"{label}은 {ratio_for_zone}%로 위험 신호가 낮은 편입니다(단, 안전을 보장하지 않습니다).")

    if secured_ratio is not None:
        # 낙찰가율(B) 안내: A(시세 기준)로 계산하되, 실제 경매 위험을 사용자에게 고지
        signals.append("경매 낙찰가는 통상 시세의 70~80% 수준이라, 실제 보증금 회수 위험은 위 수치보다 더 클 수 있습니다.")
    else:
        signals.append("등기부 을구의 근저당 채권최고액을 알려주시면 회수부담률까지 반영해 더 정확히 분석합니다.")

    if confidence in (Confidence.LOW, Confidence.NONE) or property_type == "villa":
        signals.append(f"비교 매매 표본이 {sample_count}건으로 시세 신뢰도가 낮아, 위 수치는 참고용입니다.")

    guarantee = estimate_guarantee(deposit, median_price, senior_debt, senior_deposit)

    return RiskAssessment(
        jeonse_ratio=jeonse_ratio, zone=zone, confidence=confidence,
        sample_count=sample_count, median_price=median_price,
        secured_ratio=secured_ratio, senior_debt=senior_debt or 0, senior_deposit=senior_deposit or 0,
        guarantee=guarantee,
        signals=signals, verify_items=verify,
    )
