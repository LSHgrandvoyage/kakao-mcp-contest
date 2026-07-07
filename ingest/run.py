"""ingest 오케스트레이션 — 강남구 최근 6개월 × 4 API 를 로컬 SQLite 로 사전적재.

실행:
    cp .env.example .env   # MOLIT_SERVICE_KEY 채우기
    pip install -r requirements.txt
    python -m ingest.run

산출물: data/lease.db (커밋 대상). 런타임 서버는 이 파일만 읽는다.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from . import config, store
from .client import MolitApiError, MolitClient
from .iros_client import IrosApiError, IrosClient
from .normalize import to_record


def main() -> int:
    load_dotenv()
    key = os.getenv("MOLIT_SERVICE_KEY", "")
    lawds = config.LAWD_CDS
    months = config.recent_months()

    try:
        client = MolitClient(key)
    except MolitApiError as e:
        print(f"[에러] {e}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = store.connect(config.DB_PATH)
    store.init_schema(conn)

    print(f"대상: 시군구 {len(lawds)}개, 기간={months[0]}~{months[-1]} ({len(months)}개월), 소스 {len(config.SOURCES)}종")
    print(f"  예상 호출 ≈ {len(lawds) * len(config.SOURCES) * len(months)}회")
    total_inserted = 0
    for lawd in lawds:
        gu = config.SEOUL_DISTRICTS.get(lawd, lawd)
        gu_inserted = 0
        for src in config.SOURCES:
            for ymd in months:
                try:
                    items = client.fetch_all(src["endpoint"], lawd, ymd)
                except MolitApiError as e:
                    print(f"  [경고] {gu} {src['property_type']}/{src['deal_type']} {ymd} 실패: {e}", file=sys.stderr)
                    continue
                records = [r for it in items
                           if (r := to_record(it, src["property_type"], src["deal_type"]))]
                gu_inserted += store.insert_records(conn, records)
        print(f"  {gu:8} +{gu_inserted}건")
        total_inserted += gu_inserted

    n_stats = store.build_price_stats(conn)
    print(f"\n신규 적재 {total_inserted}건, price_stats {n_stats}그룹 산출")

    # 지역 위험 지표(등기정보광장) — 키 있을 때만. 없어도 실거래 적재는 정상 완료.
    iros_key = os.getenv("IROS_SERVICE_KEY", "")
    if iros_key and not iros_key.startswith("여기에"):
        try:
            iros = IrosClient(iros_key)
            months = config.recent_months(12)
            for m in config.IROS_METRICS:
                rows = iros.fetch_monthly(config.IROS_URL, m["id"], config.IROS_REGN1,
                                          config.IROS_REGN2, config.IROS_REAL_CLS,
                                          months[0], months[-1])
                store.insert_area_risk(conn, config.IROS_REGN2 or config.IROS_REGN1,
                                       config.IROS_REGION_NAME, m["label"], rows)
                print(f"  지역위험 {m['label']:22} +{len(rows)}개월")
        except IrosApiError as e:
            print(f"  [경고] 지역위험 적재 실패(무시): {e}", file=sys.stderr)
    else:
        print("  [안내] IROS_SERVICE_KEY 없음 — 지역위험 지표 건너뜀")

    print("요약:", store.summary(conn))
    print(f"→ {config.DB_PATH}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
