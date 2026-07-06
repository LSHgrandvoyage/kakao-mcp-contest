"""domain.policy 단위 테스트 — 순수 로직, API 무관.
실행: python -m tests.test_policy   (또는 pytest)
"""
from domain import policy
from domain.policy import Confidence, Guarantee, RiskZone, assess


def test_ratio_and_zone_high_signal():
    # 전세 4.6억 / 시세 5억 = 92% → 고위험 신호
    r = assess(deposit=460_000_000, median_price=500_000_000, sample_count=6, property_type="apartment")
    assert r.jeonse_ratio == 92.0
    assert r.zone == RiskZone.HIGH_SIGNAL
    assert r.confidence == Confidence.HIGH
    assert any("고위험" in s for s in r.signals)


def test_zone_caution_boundary():
    # 정확히 70% → 주의 구간(경계 포함)
    r = assess(deposit=350_000_000, median_price=500_000_000, sample_count=3, property_type="apartment")
    assert r.zone == RiskZone.CAUTION
    assert r.confidence == Confidence.MEDIUM


def test_zone_low_signal_not_safe():
    # 낮은 전세가율이라도 "안전" 단정 금지
    r = assess(deposit=100_000_000, median_price=1_000_000_000, sample_count=10, property_type="apartment")
    assert r.zone == RiskZone.LOW_SIGNAL
    joined = " ".join(r.signals)
    assert "안전" not in joined or "안전을 보장하지 않" in joined
    assert "안전합니다" not in joined


def test_no_price_returns_unknown_not_error():
    # 시세 못 구하면 에러 아니라 UNKNOWN + 확인 안내
    r = assess(deposit=300_000_000, median_price=None, sample_count=0, property_type="apartment")
    assert r.zone == RiskZone.UNKNOWN
    assert r.confidence == Confidence.NONE
    assert r.jeonse_ratio is None
    assert r.verify_items  # 확인 항목은 항상 제공


def test_villa_confidence_capped():
    # 빌라는 표본 많아도 최대 '보통'
    r = assess(deposit=200_000_000, median_price=400_000_000, sample_count=8, property_type="villa")
    assert r.confidence == Confidence.MEDIUM
    assert any("신뢰도가 낮" in s for s in r.signals)


def test_senior_debt_flips_zone():
    # 전세가율만이면 낮음, 근저당 포함하면 회수부담률이 올라 위험구간으로 뒤집힘
    base = assess(deposit=340_000_000, median_price=1_465_000_000, sample_count=22,
                  property_type="apartment")
    assert base.zone == RiskZone.LOW_SIGNAL and base.secured_ratio is None

    withdebt = assess(deposit=340_000_000, median_price=1_465_000_000, sample_count=22,
                      property_type="apartment", senior_debt=800_000_000)
    assert withdebt.jeonse_ratio == base.jeonse_ratio          # 전세가율은 그대로
    assert withdebt.secured_ratio is not None and withdebt.secured_ratio > 70
    assert withdebt.zone == RiskZone.CAUTION                    # (800+340)/1465 = 77.8% → 주의
    assert any("낙찰가" in s for s in withdebt.signals)         # 낙찰가율(B) 안내 포함


def test_guarantee_estimate():
    # 부채비율 낮음 → 가입 가능성 높음
    r = assess(deposit=100_000_000, median_price=1_000_000_000, sample_count=10, property_type="apartment")
    assert r.guarantee.level == Guarantee.LIKELY
    # 근저당 커서 부담률 100% 초과 + 근저당 60% 게이트 초과 → 거절 가능성
    r2 = assess(deposit=340_000_000, median_price=1_000_000_000, sample_count=10,
                property_type="apartment", senior_debt=800_000_000)
    assert r2.guarantee.level == Guarantee.UNLIKELY
    # 시세 없음 → 추정 불가
    r3 = assess(deposit=300_000_000, median_price=None, sample_count=0, property_type="apartment")
    assert r3.guarantee.level == Guarantee.UNKNOWN


def test_disclaimer_always_present():
    for mp, sc in [(500_000_000, 6), (None, 0)]:
        r = assess(deposit=300_000_000, median_price=mp, sample_count=sc, property_type="apartment")
        assert r.disclaimer and "법률 자문" in r.disclaimer


def _run():
    fns = [v for k, v in globals().items() if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✅ {fn.__name__}")
    print(f"\n{len(fns)}개 테스트 전부 통과")


if __name__ == "__main__":
    _run()
