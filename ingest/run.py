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
from .normalize import to_record


def main() -> int:
    load_dotenv()
    key = os.getenv("MOLIT_SERVICE_KEY", "")
    lawd = config.DEFAULT_LAWD_CD
    months = config.recent_months()

    try:
        client = MolitClient(key)
    except MolitApiError as e:
        print(f"[에러] {e}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = store.connect(config.DB_PATH)
    store.init_schema(conn)

    print(f"대상: LAWD_CD={lawd}, 기간={months[0]}~{months[-1]} ({len(months)}개월), 소스 {len(config.SOURCES)}종")
    total_inserted = 0
    for src in config.SOURCES:
        label = f"{src['property_type']}/{src['deal_type']}"
        src_inserted = 0
        for ymd in months:
            try:
                items = client.fetch_all(src["endpoint"], lawd, ymd)
            except MolitApiError as e:
                print(f"  [경고] {label} {ymd} 실패: {e}", file=sys.stderr)
                continue
            records = [r for it in items
                       if (r := to_record(it, src["property_type"], src["deal_type"]))]
            src_inserted += store.insert_records(conn, records)
        print(f"  {label:18} +{src_inserted}건")
        total_inserted += src_inserted

    n_stats = store.build_price_stats(conn)
    print(f"\n신규 적재 {total_inserted}건, price_stats {n_stats}그룹 산출")
    print("요약:", store.summary(conn))
    print(f"→ {config.DB_PATH}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
