from concurrent.futures import ThreadPoolExecutor

from app.services.login_limits import LocalLoginLimits


def test_outage_limit_expires_without_sliding_window():
    now = [10.0]
    limiter = LocalLoginLimits(clock=lambda: now[0])
    assert limiter.allow('account', 2, 60)
    now[0] = 69
    assert limiter.allow('account', 2, 60)
    assert not limiter.allow('account', 2, 60)
    now[0] = 70
    assert limiter.allow('account', 2, 60)


def test_memory_bound_does_not_evict_active_limits():
    now = [0]
    limiter = LocalLoginLimits(max_keys=2, clock=lambda: now[0])
    assert limiter.allow('a', 1, 60)
    assert limiter.allow('b', 1, 60)
    assert not limiter.allow('c', 1, 60)
    assert not limiter.allow('a', 1, 60)
    now[0] = 60
    assert limiter.allow('c', 1, 60)
    limiter.clear('c')
    assert limiter.allow('c', 1, 60)


def test_parallel_attempts_cannot_race_limit():
    limiter = LocalLoginLimits()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: limiter.allow('a', 10, 60), range(40)))
    assert sum(results) == 10
