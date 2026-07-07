"""등기정보광장(data.iros.go.kr) 클라이언트 — 지역 위험 지표용.

임차권등기명령 신청 부동산 현황(집합건물·시군구·월별) 통계를 가져온다.
※ 개별 매물 등기부가 아니라 '지역 집계' 통계다(개별 등기부는 이 API에 없음).
응답 구조(실물 확인): {"result":{"head":{"returnCode":"APIINFO-0001"},"items":{"item":[{resDate,tot,...}]}}}
"""
from __future__ import annotations

from urllib.parse import urlencode

import requests

_UA = "Mozilla/5.0 (compatible; LeaseGuideIngest/0.1)"
_OK_PREFIX = "APIINFO-0001"


class IrosApiError(RuntimeError):
    pass


class IrosClient:
    def __init__(self, key: str, *, timeout: int = 20):
        if not key or key.startswith("여기에"):
            raise IrosApiError("IROS_SERVICE_KEY 가 설정되지 않았습니다 (.env 확인).")
        self._key = key
        self._timeout = timeout

    def fetch_monthly(self, url: str, api_id: str, regn1: str, regn2: str,
                      real_cls: str, start_ym: str, end_ym: str) -> list[dict]:
        """월별(YYYYMM~YYYYMM) 지역 통계를 [{'ym': 'YYYY-MM', 'cnt': int}] 로 반환."""
        params = {
            "id": api_id, "reqtype": "json",
            "search_type_api": "02",  # 월별
            "search_start_date_api": start_ym, "search_end_date_api": end_ym,
            "search_regn1_name_api": regn1,
            "search_real_cls_api": real_cls,
        }
        if regn2:  # 시군구 코드 있을 때만(빈값이면 시도 전체)
            params["search_regn2_name_api"] = regn2
        # key 는 재인코딩 방지를 위해 raw 로 붙인다(국토부 클라이언트와 동일 방침).
        full = f"{url}?key={self._key}&{urlencode(params)}"
        try:
            resp = requests.get(full, headers={"User-Agent": _UA}, timeout=self._timeout)
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            raise IrosApiError(f"요청/파싱 실패: {e}")

        result = data.get("result") or {}
        code = (result.get("head") or {}).get("returnCode", "")
        if code and not code.startswith(_OK_PREFIX):
            msg = (result.get("head") or {}).get("returnMessage", "unknown")
            raise IrosApiError(f"API 오류 {code}: {msg}")

        items = (result.get("items") or {}).get("item") or []
        if isinstance(items, dict):  # 단건이면 dict 로 옴
            items = [items]
        # 월별로 합산(시도 전체 조회 시 구별 여러 행이 와도 견고하게)
        agg: dict[str, int] = {}
        for it in items:
            ym = (it.get("resDate") or "").strip()
            tot = (it.get("tot") or "").strip()
            if ym and tot.isdigit():
                agg[ym] = agg.get(ym, 0) + int(tot)
        return [{"ym": ym, "cnt": cnt} for ym, cnt in sorted(agg.items())]
