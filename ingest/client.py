"""국토부 실거래가 API 클라이언트.

주의점(실물 검증에서 확인):
- data.go.kr 게이트웨이는 curl/기본 UA를 WAF로 차단한다 → User-Agent 필수.
- serviceKey(Encoding)는 이미 URL 인코딩돼 있으므로 재인코딩하면 깨진다 → URL에 raw로 붙인다.
"""
from __future__ import annotations

import time
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import requests

_UA = "Mozilla/5.0 (compatible; LeaseGuideIngest/0.1)"
_OK_CODES = {"00", "000"}
_PAGE_SIZE = 1000
_MAX_PAGES = 50


class MolitApiError(RuntimeError):
    pass


class MolitClient:
    def __init__(self, service_key: str, *, timeout: int = 20, retries: int = 2):
        if not service_key or service_key.startswith("여기에"):
            raise MolitApiError("MOLIT_SERVICE_KEY 가 설정되지 않았습니다 (.env 확인).")
        self._key = service_key
        self._timeout = timeout
        self._retries = retries

    def _get(self, endpoint: str, params: dict) -> str:
        # serviceKey 는 재인코딩 방지를 위해 직접 붙이고, 나머지만 urlencode.
        url = f"{endpoint}?serviceKey={self._key}&{urlencode(params)}"
        last_exc = None
        for attempt in range(self._retries + 1):
            try:
                resp = requests.get(url, headers={"User-Agent": _UA}, timeout=self._timeout)
                text = resp.text
                if "Request Blocked" in text or "<TITLE>" in text.upper()[:200]:
                    raise MolitApiError("게이트웨이(WAF)에 차단됨 — User-Agent/네트워크 확인.")
                return text
            except requests.RequestException as e:
                last_exc = e
                time.sleep(1.0 * (attempt + 1))
        raise MolitApiError(f"요청 실패: {last_exc}")

    @staticmethod
    def _parse(text: str) -> tuple[list[ET.Element], int]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise MolitApiError(f"XML 파싱 실패(응답이 XML이 아님): {e}")
        code = (root.findtext(".//header/resultCode") or "").strip()
        if code not in _OK_CODES:
            msg = (root.findtext(".//header/resultMsg")
                   or root.findtext(".//cmmMsgHeader/errMsg") or "unknown")
            raise MolitApiError(f"API 오류 resultCode={code!r}: {msg}")
        items = root.findall(".//items/item")
        total = int(root.findtext(".//totalCount") or "0")
        return items, total

    def fetch_all(self, endpoint: str, lawd_cd: str, deal_ymd: str) -> list[dict]:
        """해당 (지역, 계약월)의 전체 거래를 페이징으로 모아 dict 리스트로 반환."""
        collected: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            text = self._get(endpoint, {
                "LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd,
                "pageNo": page, "numOfRows": _PAGE_SIZE,
            })
            items, total = self._parse(text)
            if not items:
                break
            collected.extend({child.tag: (child.text or "").strip() for child in it}
                             for it in items)
            if len(collected) >= total:
                break
        return collected
