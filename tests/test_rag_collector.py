from apps.rag.collector import collect


def test_collect_returns_docs(monkeypatch):
    docs = collect("btc", 60)
    assert isinstance(docs, list)
    if docs:
        d0 = docs[0]
        assert "url" in d0 and "timestamp" in d0

