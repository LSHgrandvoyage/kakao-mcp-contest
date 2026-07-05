"""마켓 데이터 조회 계층 — lease.db(read-only) 접근. 도메인 로직과 데이터 접근 분리(brief §7 DIP).

- resolve_building: 단지명 + 동 → building_key (입력 방식 A). transactions 의 실제 단지명과 매칭.
- price_stat: building_key + 전용면적 → 사전집계 시세(중앙값, 표본수). 인덱스 조회, 외부호출 0.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass


@dataclass
class BuildingMatch:
    building_key: str
    building_name: str
    umd: str
    txn_count: int


def open_readonly(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _norm(s: str) -> str:
    """단지명 정규화: 공백·괄호(동 표기)·'아파트' 접미어 제거."""
    s = re.sub(r"\(.*?\)", "", s or "")      # (102동) 등 제거
    s = s.replace(" ", "")
    s = re.sub(r"아파트$", "", s)
    return s.strip()


class MarketRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def resolve_building(self, name: str, umd: str, property_type: str) -> BuildingMatch | None:
        """동 안에서 단지명이 매칭되는 건물 중 거래가 가장 많은(= 가장 그럴듯한) 것."""
        target = _norm(name)
        if not target:
            return None
        rows = self._conn.execute(
            "SELECT building_key, building_name, umd, COUNT(*) c "
            "FROM transactions WHERE property_type=? AND umd LIKE ? "
            "AND building_name IS NOT NULL "
            "GROUP BY building_key, building_name, umd",
            (property_type, f"%{umd.strip()}%"),
        ).fetchall()

        best: BuildingMatch | None = None
        for r in rows:
            cand = _norm(r["building_name"])
            if not cand:
                continue
            if target in cand or cand in target:
                m = BuildingMatch(r["building_key"], r["building_name"], r["umd"], r["c"])
                if best is None or m.txn_count > best.txn_count:
                    best = m
        return best

    def price_stat(self, property_type: str, building_key: str, area: float) -> tuple[int | None, int]:
        """(median_price, sample_count). 정확 버킷 우선, 없으면 ±1㎡ 버킷 폴백."""
        bucket = round(area)
        for b in (bucket, bucket - 1, bucket + 1):
            row = self._conn.execute(
                "SELECT median_price, sample_count FROM price_stats "
                "WHERE property_type=? AND building_key=? AND area_bucket=?",
                (property_type, building_key, b),
            ).fetchone()
            if row:
                return row["median_price"], row["sample_count"]
        return None, 0
