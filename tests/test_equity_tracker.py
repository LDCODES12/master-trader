from apps.analytics.equity import update_equity


def test_update_equity_runs(monkeypatch):
    from apps.analytics import equity as eq

    monkeypatch.setattr(eq, "_price", lambda s: 50000.0)
    out = update_equity(mark_only=True)
    assert "equity" in out and "hwm" in out and "mdd" in out

