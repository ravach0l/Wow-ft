from types import SimpleNamespace as S

from wowft import metrics


def test_totals():
    assert metrics.total_xp(1, 0) == 0
    assert metrics.total_xp(2, 100) == 500
    assert metrics.xp_to_max(60, 0, 60) == 0
    assert metrics.xp_before_level(60) == sum(metrics.XP_TO_NEXT.values())


def test_rate_needs_enough_playtime():
    snaps = [S(level=10, xp=0, played_total=1000), S(level=10, xp=500, played_total=1100)]
    assert metrics.xp_per_hour(snaps) is None
    snaps = [S(level=10, xp=0, played_total=1000), S(level=10, xp=3000, played_total=4600)]
    assert metrics.xp_per_hour(snaps) == 3000


def test_rate_uses_window():
    old = S(level=5, xp=0, played_total=0)
    recent = S(level=20, xp=0, played_total=100_000)
    last = S(level=20, xp=7200, played_total=100_000 + 7200)
    assert metrics.xp_per_hour([old, recent, last]) == 3600


def test_eta():
    assert metrics.eta_seconds(60, 0, None, 60) == 0
    assert metrics.eta_seconds(59, 0, None, 60) is None
    assert metrics.eta_seconds(59, 0, 209800, 60) == 3600
