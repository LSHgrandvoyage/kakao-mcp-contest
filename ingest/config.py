"""ingest 설정 상수 — 대상 지역·기간·데이터 소스 정의.

constitution §3-1(사전적재)·plan §2-1 준수. 임계값/상수는 코드에 하드코딩하지 않고
여기 한 곳에 모아 설정으로 분리한다(brief §7 OCP).
"""
from __future__ import annotations

import os
from datetime import date

# 대상: 서울 전체 25개 자치구 (법정동코드 앞 5자리 = 시군구 코드)
SEOUL_DISTRICTS = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}
# env로 특정 구만 지정 가능(예: "11680,11650"). 미지정 시 서울 전체.
LAWD_CDS = os.getenv("LAWD_CDS", ",".join(SEOUL_DISTRICTS)).split(",")
SIGUNGU_TO_CODE = {name: code for code, name in SEOUL_DISTRICTS.items()}

# 적재 기간(최근 N개월). spec §4 확정: 6개월.
DEFAULT_MONTHS = int(os.getenv("MONTHS", "6"))

# 국토부 실거래가 오픈API (data.go.kr, 기관코드 1613000). 4종.
# property_type: apartment|villa,  deal_type: trade(매매)|rent(전월세)
BASE = "https://apis.data.go.kr/1613000"
SOURCES = [
    {
        "property_type": "apartment",
        "deal_type": "rent",
        "endpoint": f"{BASE}/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
    },
    {
        "property_type": "apartment",
        "deal_type": "trade",
        "endpoint": f"{BASE}/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    },
    {
        "property_type": "villa",
        "deal_type": "rent",
        "endpoint": f"{BASE}/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    },
    {
        "property_type": "villa",
        "deal_type": "trade",
        "endpoint": f"{BASE}/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
    },
]

# 산출물 경로 (커밋 대상 — 이미지 동봉)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lease.db")

# ── 등기정보광장(data.iros.go.kr) — 지역 위험 지표 (선택) ──
# 개별 매물이 아니라 시군구 월별 통계. 강남구 임차권등기명령(집합건물) 추세를 지역 신호로 사용.
IROS_URL = "https://data.iros.go.kr/openapi/cr/rs/selectCrRsRgsCsOpenApi.rest"
IROS_REGN1 = os.getenv("IROS_REGN1", "900")   # 서울특별시
IROS_REGN2 = os.getenv("IROS_REGN2", "")      # 빈값 = 서울 전체 (구별 코드 있으면 지정)
IROS_REGION_NAME = os.getenv("IROS_REGION_NAME", "서울")
IROS_REAL_CLS = "02"                          # 집합건물(아파트+빌라)
IROS_METRICS = [
    {"id": "0000000079", "label": "임차권등기명령(집합건물)"},
]


def recent_months(n: int = DEFAULT_MONTHS, today: date | None = None) -> list[str]:
    """오늘 기준 최근 n개월을 'YYYYMM' 문자열 리스트로 (오래된 → 최신)."""
    today = today or date.today()
    y, m = today.year, today.month
    out: list[str] = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))
