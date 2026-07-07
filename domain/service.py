"""서비스 조합 — repository(데이터) + policy(판정)를 엮어 진단 결과를 만든다.

tool(server 계층)은 이 결과를 마크다운으로 정제만 하면 된다.
"""
from __future__ import annotations

from dataclasses import dataclass

from ingest.config import SIGUNGU_TO_CODE
from .area import AreaSignal, build_signal
from .policy import RiskAssessment, RiskZone, Confidence, DISCLAIMER, assess
from .repository import BuildingMatch, MarketRepository

_AREA_METRIC = "임차권등기명령(집합건물)"
_AREA_REGION = "서울"


@dataclass
class DiagnoseResult:
    matched: BuildingMatch | None
    assessment: RiskAssessment
    query_area: float
    area_signal: AreaSignal | None = None


def diagnose_lease_risk(repo: MarketRepository, *, property_type: str,
                        building_name: str, umd: str, deposit: int,
                        exclusive_area: float, senior_debt: int = 0,
                        senior_deposit: int = 0, sigungu: str | None = None) -> DiagnoseResult:
    """단지명+동(+구)+보증금+전용면적(+선택: 등기부 선순위) → 위험 진단. 시세 못 찾으면 UNKNOWN."""
    # 지역 위험 신호(서울 전체) — 개별 매물과 무관하게 항상 계산
    area = build_signal(_AREA_REGION, _AREA_METRIC, repo.area_series(_AREA_METRIC))

    sgg_code = SIGUNGU_TO_CODE.get(sigungu.strip()) if sigungu else None
    match = repo.resolve_building(building_name, umd, property_type, sgg_code)
    if match is None:
        where = f"{sigungu} {umd}".strip() if sigungu else umd
        a = assess(deposit, None, 0, property_type, senior_debt, senior_deposit)
        a.signals.insert(0, f"'{where} {building_name}'에 해당하는 단지의 최근 실거래를 찾지 못했습니다(현재 서울만 지원).")
        return DiagnoseResult(matched=None, assessment=a, query_area=exclusive_area, area_signal=area)

    median, sample = repo.price_stat(property_type, match.building_key, exclusive_area)
    a = assess(deposit, median, sample, property_type, senior_debt, senior_deposit)
    return DiagnoseResult(matched=match, assessment=a, query_area=exclusive_area, area_signal=area)
