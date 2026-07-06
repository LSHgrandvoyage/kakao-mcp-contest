"""지역 위험 지표 도메인 로직 (순수 함수).

임차권등기명령(=보증금 미반환의 직접 흔적) 월별 건수의 최근 추세로,
'이 지역(강남구)의 전세 위험 분위기'를 신호로 만든다.
개별 매물 판단이 아니라 지역 맥락임을 명확히 한다.

임계값은 이 모듈 상단 상수로 분리(brief §7 OCP).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

RISING_RATIO = 1.2   # 최근3 / 직전3 이 1.2 이상이면 증가
FALLING_RATIO = 0.8  # 0.8 이하면 감소


class Trend(str, Enum):
    RISING = "rising"
    FLAT = "flat"
    FALLING = "falling"
    UNKNOWN = "unknown"


@dataclass
class AreaSignal:
    region: str
    metric: str
    recent_count: int   # 최근 3개월 합
    prev_count: int     # 직전 3개월 합
    trend: Trend
    latest_ym: str


def classify_trend(recent: int, prev: int) -> Trend:
    if prev <= 0:
        return Trend.RISING if recent > 0 else Trend.UNKNOWN
    ratio = recent / prev
    if ratio >= RISING_RATIO:
        return Trend.RISING
    if ratio <= FALLING_RATIO:
        return Trend.FALLING
    return Trend.FLAT


def build_signal(region: str, metric: str, series: list[tuple[str, int]]) -> AreaSignal | None:
    """series: [(ym, cnt)] (정렬 무관). 최근 6개월 필요(최근3 vs 직전3). 부족하면 None."""
    if len(series) < 6:
        return None
    s = sorted(series, key=lambda x: x[0])
    prev = sum(c for _, c in s[-6:-3])
    recent = sum(c for _, c in s[-3:])
    return AreaSignal(region, metric, recent, prev, classify_trend(recent, prev), s[-1][0])


def area_message(sig: AreaSignal) -> str:
    base = f"최근 3개월 {sig.region} {sig.metric} {sig.recent_count}건(직전 3개월 {sig.prev_count}건)"
    if sig.trend == Trend.RISING:
        return f"⚠️ {base} — 증가 추세로, 지역 차원의 전세 위험이 커지고 있습니다."
    if sig.trend == Trend.FALLING:
        return f"{base} — 감소 추세입니다."
    if sig.trend == Trend.FLAT:
        return f"{base} — 큰 변동은 없습니다."
    return f"{base}."
