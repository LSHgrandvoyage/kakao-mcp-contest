"""Lease Guide(전월세 길잡이) MCP 서버 — FastMCP / streamable-http.

tool 3개. 요청 핫패스는 로컬 lease.db 조회만(constitution §3-1). 무세션·stateless.
각 tool 은 annotations 5필드를 전부 지정하고, 출력은 정제된 마크다운이다(constitution §2·§3).
"""
from __future__ import annotations

import os
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from domain.area import area_message
from domain.policy import Confidence, Guarantee, RiskZone
from domain.repository import MarketRepository, open_readonly
from domain.service import DiagnoseResult, diagnose_lease_risk as _diagnose_service
from ingest.config import DB_PATH
from server import content

mcp = FastMCP("Lease Guide")

_ZONE_KR = {
    RiskZone.HIGH_SIGNAL: "고위험 신호", RiskZone.CAUTION: "주의",
    RiskZone.LOW_SIGNAL: "위험 신호 낮음", RiskZone.UNKNOWN: "시세 산정 불가",
}
_CONF_KR = {Confidence.NONE: "없음", Confidence.LOW: "낮음",
            Confidence.MEDIUM: "보통", Confidence.HIGH: "높음"}
_GUAR_KR = {Guarantee.LIKELY: "가능성 높음", Guarantee.BORDERLINE: "경계(조건 확인 필요)",
            Guarantee.UNLIKELY: "거절 가능성 있음", Guarantee.UNKNOWN: "추정 불가"}


def _won(n: int | None) -> str:
    if not n:
        return "-"
    eok, man = n // 100_000_000, (n % 100_000_000) // 10_000
    return f"{eok}억 {man:,}만원" if man else f"{eok}억원"


def _repo() -> tuple[MarketRepository, object]:
    conn = open_readonly(DB_PATH)  # read-only, 요청마다 새로(무상태·스레드 안전)
    return MarketRepository(conn), conn


def _render_diagnosis(r: DiagnoseResult, monthly_rent: int) -> str:
    a = r.assessment
    lines = ["### 전월세 길잡이 · 위험 진단"]
    if r.matched:
        lines.append(f"- 대상: {r.matched.umd} {r.matched.building_name} · 전용 {r.query_area}㎡")
        if a.median_price:
            lines.append(f"- 최근 매매 시세(중앙값): {_won(a.median_price)} · 비교 표본 {a.sample_count}건")
    if a.jeonse_ratio is None:
        lines.append(f"- 전세가율: 산정 불가 → **{_ZONE_KR[a.zone]}**")
    else:
        tail = f" · 선순위 포함 회수부담률 {a.secured_ratio}%" if a.secured_ratio is not None else ""
        lines.append(f"- 전세가율: {a.jeonse_ratio}%{tail} → **{_ZONE_KR[a.zone]}**")
        if a.senior_debt or a.senior_deposit:
            parts = []
            if a.senior_debt:
                parts.append(f"근저당 채권최고액 {_won(a.senior_debt)}")
            if a.senior_deposit:
                parts.append(f"선순위 보증금 {_won(a.senior_deposit)}")
            lines.append(f"- 반영된 선순위: {' · '.join(parts)}")
    lines.append(f"- 시세 신뢰도: {_CONF_KR[a.confidence]}")
    if a.guarantee:
        lines.append(f"- 전세보증보험(HUG) 가입 가능성(추정): **{_GUAR_KR[a.guarantee.level]}**")
        lines.append(f"  · {a.guarantee.note}")
    if monthly_rent > 0:
        lines.append("- ⚠️ 월세/반전세는 보증금만으로 전세가율을 해석하면 위험이 과소평가될 수 있습니다.")

    lines.append("\n**위험 신호**")
    lines += [f"- {s}" for s in a.signals]
    if r.area_signal:
        lines.append("\n**지역 신호 (서울 전체)**")
        lines.append(f"- {area_message(r.area_signal)}")
        lines.append("- (서울 전체 통계이며, 이 매물 개별 상태는 아닙니다.)")
    lines.append("\n**직접 확인하세요**")
    lines += [f"- {v}" for v in a.verify_items]
    lines.append(f"\n> {a.disclaimer}")
    return "\n".join(lines)


@mcp.tool(
    annotations={"title": "Lease Risk Diagnosis", "readOnlyHint": True,
                 "destructiveHint": False, "openWorldHint": False, "idempotentHint": True},
    description=(
        "Analyzes lease risk signals for a rental home in Seoul with "
        "Lease Guide(전월세 길잡이). Given a building name, dong(umd), exclusive area, deposit, "
        "and property type, it computes the jeonse-to-sale-price ratio from recent real-transaction "
        "data (Ministry of Land/국토부) and returns risk-zone indicators, price-estimate confidence "
        "with comparable-transaction counts, and items to verify on the property register(등기부등본). "
        "If the user provides the senior mortgage(근저당) amount from the register, it also computes a "
        "deposit-recovery burden ratio and estimates HUG rental-guarantee(전세보증보험) eligibility. "
        "It never declares a property 'safe'; it surfaces risk signals and next verification steps only. "
        "Preliminary screening, not legal advice."
    ),
)
def diagnose_lease_risk(
    building_name: Annotated[str, Field(description="단지/건물명 (예: 은마)")],
    umd: Annotated[str, Field(description="법정동 (예: 대치동)")],
    exclusive_area: Annotated[float, Field(description="전용면적(㎡)", gt=0)],
    deposit: Annotated[int, Field(description="전세 보증금(원)", gt=0)],
    property_type: Literal["apartment", "villa"],
    sigungu: Annotated[str, Field(description="자치구 (예: 강남구). 같은 동명이 여러 구에 있을 때 구분용, 모르면 빈값")] = "",
    monthly_rent: Annotated[int, Field(description="반전세 월세(원), 순수 전세면 0", ge=0)] = 0,
    senior_debt: Annotated[int, Field(description="등기부 을구 근저당 채권최고액 합계(원). 모르면 0", ge=0)] = 0,
    senior_deposit: Annotated[int, Field(description="다가구 선순위 임차보증금 총액(원). 해당 없으면 0", ge=0)] = 0,
) -> str:
    repo, conn = _repo()
    try:
        result = _diagnose_service(
            repo, property_type=property_type, building_name=building_name,
            umd=umd, deposit=deposit, exclusive_area=exclusive_area,
            senior_debt=senior_debt, senior_deposit=senior_deposit,
            sigungu=sigungu or None,
        )
    finally:
        conn.close()
    return _render_diagnosis(result, monthly_rent)


@mcp.tool(
    annotations={"title": "Lease Stage Checklist", "readOnlyHint": True,
                 "destructiveHint": False, "openWorldHint": False, "idempotentHint": True},
    description=(
        "Provides a stage-specific action checklist for the tenant lease lifecycle with "
        "Lease Guide(전월세 길잡이). Given a lifecycle stage (property search, before contract, "
        "contract day, balance/move-in day, during residence, near expiry), it returns the ordered "
        "actions and verification items for that moment — e.g., on balance-payment day, complete "
        "resident registration(전입신고) and fixed-date stamp(확정일자) immediately, since that "
        "ordering determines when opposing power(대항력) takes effect."
    ),
)
def get_stage_checklist(
    stage: Literal["property_search", "before_contract", "contract_day",
                   "movein_day", "during_residence", "near_expiry"],
) -> str:
    s = content.STAGES[stage]
    lines = [f"### 전월세 길잡이 · {s['title']} 체크리스트", "\n**해야 할 일 (순서대로)**"]
    lines += [f"{i}. {a}" for i, a in enumerate(s["actions"], 1)]
    lines.append("\n**확인 항목**")
    lines += [f"- {v}" for v in s["verify"]]
    lines.append(f"\n> 참고: {s['notes']}")
    return "\n".join(lines)


@mcp.tool(
    annotations={"title": "Contract Clause Suggestions", "readOnlyHint": True,
                 "destructiveHint": False, "openWorldHint": False, "idempotentHint": True},
    description=(
        "Suggests special-agreement clause(특약) candidates for a lease contract with "
        "Lease Guide(전월세 길잡이). Given a described situation (e.g., newly built villa, existing "
        "senior mortgage(근저당), corporate landlord), it returns candidate clause texts with the "
        "reason each is needed. Output always includes a disclaimer that this is not legal advice and "
        "the tenant should consult a licensed real-estate agent(공인중개사)."
    ),
)
def generate_contract_clauses(
    situation: Annotated[str, Field(description="상황 서술 (예: 근저당 있는 신축 빌라, 법인 임대인)")],
) -> str:
    clauses = content.select_clauses(situation)
    lines = ["### 전월세 길잡이 · 특약 문구 제안"]
    for i, c in enumerate(clauses, 1):
        lines.append(f"\n**{i}. {c['text']}**")
        lines.append(f"   - 이유: {c['why']}")
    lines.append(f"\n> {content.CLAUSE_DISCLAIMER}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0",
            port=int(os.getenv("PORT", "8000")))
