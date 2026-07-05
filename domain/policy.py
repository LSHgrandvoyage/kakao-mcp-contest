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


@dataclass
class RiskAssessment:
    jeonse_ratio: float | None          # 전세가율(%), 시세 없으면 None
    zone: RiskZone
    confidence: Confidence
    sample_count: int
    median_price: int | None            # 매매 시세 중앙값(원)
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


def assess(deposit: int, median_price: int | None, sample_count: int,
           property_type: str) -> RiskAssessment:
    """전세 보증금 + 사전집계 시세 → 위험 평가. 순수 함수."""
    verify = list(_BASE_VERIFY)

    # 시세를 못 구한 경우: 판정하지 않고 확인을 안내(에러 아님, 제품 원칙)
    if not median_price or sample_count <= 0:
        return RiskAssessment(
            jeonse_ratio=None, zone=RiskZone.UNKNOWN, confidence=Confidence.NONE,
            sample_count=sample_count, median_price=median_price,
            signals=["최근 실거래 기준 시세를 산정할 만한 비교 거래가 부족합니다(시세 신뢰도 없음)."],
            verify_items=verify,
        )

    ratio = round(100.0 * deposit / median_price, 1)
    zone = classify_zone(ratio)
    confidence = classify_confidence(sample_count, property_type)

    signals: list[str] = []
    if zone == RiskZone.HIGH_SIGNAL:
        signals.append(f"전세가율이 {ratio}%로 고위험 신호 구간입니다(깡통전세 위험 주의).")
    elif zone == RiskZone.CAUTION:
        signals.append(f"전세가율이 {ratio}%로 주의 구간입니다.")
    else:
        signals.append(f"전세가율은 {ratio}%로 위험 신호가 낮은 편입니다(단, 안전을 보장하지 않습니다).")

    if confidence in (Confidence.LOW, Confidence.NONE) or property_type == "villa":
        signals.append(f"비교 매매 표본이 {sample_count}건으로 시세 신뢰도가 낮아, 위 수치는 참고용입니다.")

    return RiskAssessment(
        jeonse_ratio=ratio, zone=zone, confidence=confidence,
        sample_count=sample_count, median_price=median_price,
        signals=signals, verify_items=verify,
    )
