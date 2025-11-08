import os, time, httpx, feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone


TIMEOUT = float(os.getenv("RAG_TIMEOUT_S", "6"))
MAX_DOCS = int(os.getenv("RAG_MAX_DOCS", "8"))


def _norm_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())


def _http_get(url: str) -> dict:
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        text = r.text
    return {
        "url": url,
        "title": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": _norm_text(text),
        "source_type": "http",
    }


def _rss_get(url: str) -> list:
    out = []
    feed = feedparser.parse(url)
    for e in feed.entries[:MAX_DOCS]:
        title = e.get("title") or ""
        link = e.get("link") or url
        ts = None
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                ts = datetime(*e.get(k)[:6], tzinfo=timezone.utc).isoformat()
                break
        summary = _norm_text(e.get("summary", ""))
        out.append(
            {
                "url": link,
                "title": title,
                "timestamp": ts or datetime.now(timezone.utc).isoformat(),
                "text": summary,
                "source_type": "rss",
            }
        )
    return out


def collect(query: str | None = None, horizon_minutes: int = 60) -> list[dict]:
    docs = []
    rss = [s.strip() for s in os.getenv("RAG_RSS_SOURCES", "").split(",") if s.strip()]
    http = [s.strip() for s in os.getenv("RAG_HTTP_SOURCES", "").split(",") if s.strip()]
    for u in rss:
        try:
            docs.extend(_rss_get(u))
        except Exception:
            continue
        if len(docs) >= MAX_DOCS:
            break
    for u in http:
        if len(docs) >= MAX_DOCS:
            break
        try:
            docs.append(_http_get(u))
        except Exception:
            continue
    seen, unique = set(), []
    for d in docs:
        if d["url"] in seen:
            continue
        seen.add(d["url"])
        unique.append(d)
    return unique[:MAX_DOCS]


