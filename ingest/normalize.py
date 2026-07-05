"""원시 item(dict) → 정규화 레코드 + 정제 규칙 적용.

정제 규칙(plan §2-1b, 실물에서 발견):
1. 해제거래 cdealType='O' → 시세 집계 제외(excluded=1)
2. 토지임대부 landLeaseholdGbn='Y' → 제외
3. 월세(monthly_rent>0)는 전세 플래그 off (전세가율 분자에서 빠짐)
4. 중복은 store 계층 UNIQUE 인덱스로 제거

금액 파싱: 국토부 금액은 '만원 단위 + 콤마 문자열'. 예 '67,200' = 6.72억 = 672,000,000원.
"""
from __future__ import annotations


def _pick(item: dict, *names: str) -> str:
    """여러 후보 태그명 중 먼저 값이 있는 것을 반환(아파트/빌라 필드명 차이 흡수)."""
    for n in names:
        v = item.get(n)
        if v:
            return v
    return ""


def _won(raw: str) -> int | None:
    """'만원+콤마' 문자열 → 원 단위 정수. 빈 값이면 None."""
    s = (raw or "").replace(",", "").strip()
    if not s:
        return None
    try:
        return int(s) * 10_000
    except ValueError:
        return None


def _int(raw: str) -> int | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _float(raw: str) -> float | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_record(item: dict, property_type: str, deal_type: str) -> dict | None:
    """원시 item → 정규화 dict. 파싱 불가한 핵심 결측이면 None."""
    year, month, day = _int(item.get("dealYear")), _int(item.get("dealMonth")), _int(item.get("dealDay"))
    if not (year and month and day):
        return None
    deal_date = f"{year:04d}-{month:02d}-{day:02d}"

    name = _pick(item, "aptNm", "mhouseNm", "offiNm")
    jibun = _pick(item, "jibun")
    umd = _pick(item, "umdNm")
    area = _float(_pick(item, "excluUseAr"))

    # 건물 식별 키: 아파트는 aptSeq(신뢰), 빌라는 없으므로 합성.
    apt_seq = _pick(item, "aptSeq")
    building_key = apt_seq or f"{umd}|{jibun}|{name}|{property_type}"

    price_amount = _won(item.get("dealAmount")) if deal_type == "trade" else None
    deposit = _won(item.get("deposit")) if deal_type == "rent" else None
    monthly_rent = _won(item.get("monthlyRent")) if deal_type == "rent" else None
    is_jeonse = 1 if (deal_type == "rent" and (monthly_rent or 0) == 0 and deposit) else 0

    # 정제 규칙 1·2: 해제거래(cdealType=O)·토지임대부는 시세 집계에서 제외.
    # 두 플래그를 분리 저장하고, 시세 집계 쿼리에서 (cancelled=0 AND land_lease=0)으로 거른다.
    # store 계층 upsert 가 MAX 로 sticky 처리하므로, 같은 거래의 원본+해제본이 합쳐져도
    # cancelled=1 이 유지된다(순서 무관).
    cancelled = 1 if _pick(item, "cdealType").upper() == "O" else 0
    land_lease = 1 if _pick(item, "landLeaseholdGbn").upper() == "Y" else 0

    return {
        "property_type": property_type,
        "deal_type": deal_type,
        "building_key": building_key,
        "apt_seq": apt_seq or None,
        "building_name": name or None,
        "umd": umd or None,
        "jibun": jibun or None,
        "road_name": _pick(item, "roadnm", "roadNm") or None,
        "excl_area": area,
        "floor": _int(item.get("floor")),
        "build_year": _int(item.get("buildYear")),
        "deal_date": deal_date,
        "price_amount": price_amount,
        "deposit": deposit,
        "monthly_rent": monthly_rent,
        "is_jeonse": is_jeonse,
        "cancelled": cancelled,
        "land_lease": land_lease,
    }
