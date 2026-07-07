"""SQLite 적재 계층 — 스키마·삽입·인덱스·시세 사전집계.

- transactions: 정규화된 실거래(매매+전월세 통합, 타입 컬럼으로 구분)
- price_stats: (property_type, building_key, area_bucket)별 매매가 중앙값 + 표본수 (사전집계)
  → 런타임 전세가율 계산이 재집계 없이 조회 한 번으로 끝난다(constitution §3 성능).

멱등성/중복 제거(정제 규칙 4): 결정적 nat_key 를 UNIQUE 로 두고 upsert.
  - 재실행해도 중복이 쌓이지 않는다.
  - 해제거래는 원본+해제본이 같은 nat_key 로 합쳐지며, cancelled 를 MAX 로 sticky 처리해
    (원본이 먼저 들어와도) cancelled=1 이 유지된다. → 취소된 시세가 절대 집계에 안 들어감.
median 은 SQLite 내장이 없어 Python 에서 계산해 저장한다.
"""
from __future__ import annotations

import sqlite3
from statistics import median

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_key       TEXT NOT NULL UNIQUE,
    property_type TEXT NOT NULL,
    deal_type     TEXT NOT NULL,
    building_key  TEXT NOT NULL,
    sgg_code      TEXT,
    apt_seq       TEXT,
    building_name TEXT,
    umd           TEXT,
    jibun         TEXT,
    road_name     TEXT,
    excl_area     REAL,
    floor         INTEGER,
    build_year    INTEGER,
    deal_date     TEXT NOT NULL,
    price_amount  INTEGER,
    deposit       INTEGER,
    monthly_rent  INTEGER,
    is_jeonse     INTEGER NOT NULL DEFAULT 0,
    cancelled     INTEGER NOT NULL DEFAULT 0,
    land_lease    INTEGER NOT NULL DEFAULT 0
);

-- 조회 인덱스(constitution §3-1: 로컬 조회는 인덱스 필수)
CREATE INDEX IF NOT EXISTS ix_txn_lookup   ON transactions (building_key, excl_area);
CREATE INDEX IF NOT EXISTS ix_txn_sgg_umd  ON transactions (sgg_code, umd);
CREATE INDEX IF NOT EXISTS ix_txn_umd_name ON transactions (umd, property_type);

CREATE TABLE IF NOT EXISTS price_stats (
    property_type TEXT NOT NULL,
    building_key  TEXT NOT NULL,
    area_bucket   INTEGER NOT NULL,
    median_price  INTEGER NOT NULL,
    sample_count  INTEGER NOT NULL,
    PRIMARY KEY (property_type, building_key, area_bucket)
);

-- 지역 위험 지표(등기정보광장 통계). 개별 매물 아님, 시군구 월별 집계.
CREATE TABLE IF NOT EXISTS area_risk (
    region_code TEXT NOT NULL,
    region_name TEXT NOT NULL,
    metric      TEXT NOT NULL,
    ym          TEXT NOT NULL,
    cnt         INTEGER NOT NULL,
    PRIMARY KEY (region_code, metric, ym)
);
"""

# nat_key 를 제외한 값 컬럼(정규화 레코드 dict 의 키와 일치)
_COLS = [
    "property_type", "deal_type", "building_key", "sgg_code", "apt_seq", "building_name",
    "umd", "jibun", "road_name", "excl_area", "floor", "build_year",
    "deal_date", "price_amount", "deposit", "monthly_rent", "is_jeonse",
    "cancelled", "land_lease",
]

# 거래 동일성을 정하는 자연키 필드(해제 플래그는 제외 → 원본/해제본이 한 행으로 합쳐짐)
_NAT_FIELDS = [
    "property_type", "deal_type", "building_key", "excl_area", "floor",
    "deal_date", "price_amount", "deposit", "monthly_rent",
]


def _nat_key(r: dict) -> str:
    return "|".join("" if r.get(f) is None else str(r.get(f)) for f in _NAT_FIELDS)


def area_bucket(area: float | None) -> int | None:
    """전용면적 → 정수 버킷(반올림 ㎡). 같은 평형을 한 그룹으로."""
    return None if area is None else round(area)


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def insert_records(conn: sqlite3.Connection, records: list[dict]) -> int:
    cols = ["nat_key", *_COLS]
    sql = (
        f"INSERT INTO transactions ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)}) "
        f"ON CONFLICT(nat_key) DO UPDATE SET "
        f"  cancelled  = MAX(cancelled,  excluded.cancelled), "
        f"  land_lease = MAX(land_lease, excluded.land_lease)"
    )
    before = conn.total_changes
    conn.executemany(sql, [[_nat_key(r), *[r.get(c) for c in _COLS]] for r in records])
    conn.commit()
    return conn.total_changes - before


def build_price_stats(conn: sqlite3.Connection) -> int:
    """매매(trade) 중 해제·토지임대부 제외 거래를 (타입,건물키,면적버킷)으로 묶어 중앙값 산출."""
    conn.execute("DELETE FROM price_stats")
    rows = conn.execute(
        "SELECT property_type, building_key, excl_area, price_amount "
        "FROM transactions "
        "WHERE deal_type='trade' AND cancelled=0 AND land_lease=0 "
        "AND price_amount IS NOT NULL AND excl_area IS NOT NULL"
    ).fetchall()

    groups: dict[tuple, list[int]] = {}
    for r in rows:
        key = (r["property_type"], r["building_key"], area_bucket(r["excl_area"]))
        groups.setdefault(key, []).append(r["price_amount"])

    payload = [
        (pt, bk, ab, int(median(prices)), len(prices))
        for (pt, bk, ab), prices in groups.items()
    ]
    conn.executemany(
        "INSERT INTO price_stats (property_type, building_key, area_bucket, "
        "median_price, sample_count) VALUES (?, ?, ?, ?, ?)", payload
    )
    conn.commit()
    return len(payload)


def insert_area_risk(conn: sqlite3.Connection, region_code: str, region_name: str,
                     metric: str, rows: list[dict]) -> int:
    """지역 위험 통계 적재. rows: [{'ym': 'YYYY-MM', 'cnt': int}]. 멱등 upsert."""
    payload = [(region_code, region_name, metric, r["ym"], r["cnt"]) for r in rows]
    conn.executemany(
        "INSERT INTO area_risk (region_code, region_name, metric, ym, cnt) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(region_code, metric, ym) DO UPDATE SET cnt=excluded.cnt",
        payload,
    )
    conn.commit()
    return len(payload)


def summary(conn: sqlite3.Connection) -> dict:
    def one(q: str) -> int:
        return conn.execute(q).fetchone()[0]
    return {
        "transactions": one("SELECT COUNT(*) FROM transactions"),
        "trade": one("SELECT COUNT(*) FROM transactions WHERE deal_type='trade'"),
        "rent": one("SELECT COUNT(*) FROM transactions WHERE deal_type='rent'"),
        "jeonse": one("SELECT COUNT(*) FROM transactions WHERE is_jeonse=1"),
        "cancelled": one("SELECT COUNT(*) FROM transactions WHERE cancelled=1"),
        "price_stats": one("SELECT COUNT(*) FROM price_stats"),
    }
