from langgraph.graph import StateGraph, END
from pydantic import BaseModel, ValidationError
import json, os, pathlib
from langchain_openai import ChatOpenAI
from libs.schemas.proposal import Proposal, RiskParams, Evidence
from apps.rag.collector import collect


class State(dict):
    pass


def node_reader(s: State):
    mode = os.getenv("AGENT_MODE", "deterministic").lower()
    docs = collect(query=s.get("text", ""), horizon_minutes=int(s.get("horizon_minutes", 120)))
    return {"notes": f"{len(docs)} docs retrieved", "docs": docs}


def node_proposer(s: State):
    # In deterministic mode, emit a fixed draft JSON string
    mode = os.getenv("AGENT_MODE", "deterministic").lower()
    if mode != "llm":
        draft = Proposal(
            action="open",
            symbol="BTCUSDT",
            side="buy",
            size_bps_equity=4.0,
            horizon_minutes=120,
            thesis="ETF inflow headline",
            risk=RiskParams(stop_loss_bps=60, take_profit_bps=120, max_slippage_bps=3),
            evidence=[Evidence(url="https://example.com", type="news_headline")],
            confidence=0.74,
        ).model_dump()
        return {"draft": json.dumps(draft)}
    # LLM path
    try:
        _ = os.environ.get("OPENAI_API_KEY")
        if not _:
            raise RuntimeError("missing OPENAI_API_KEY")
        llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
        prompt_path = pathlib.Path(__file__).parent / "prompts" / "proposer.md"
        prompt = prompt_path.read_text()
        docs = s.get("docs", [])
        content = f"{prompt}\n\nDocs: {json.dumps(docs)[:4000]}\n\nOutput strictly JSON for Proposal."
        res = llm.invoke(content)
        return {"draft": res.content}
    except Exception:
        # fallback to stub on any error
        draft = Proposal(
            action="open",
            symbol="BTCUSDT",
            side="buy",
            size_bps_equity=4.0,
            horizon_minutes=120,
            thesis="ETF inflow headline",
            risk=RiskParams(stop_loss_bps=60, take_profit_bps=120, max_slippage_bps=3),
            evidence=[Evidence(url="https://example.com", type="news_headline")],
            confidence=0.74,
        ).model_dump()
        return {"draft": json.dumps(draft)}


def node_skeptic(s: State):
    mode = os.getenv("AGENT_MODE", "deterministic").lower()
    if mode != "llm":
        return {"critique": "risk acceptable; check slippage; ensure evidence cites official source"}
    try:
        _ = os.environ.get("OPENAI_API_KEY")
        if not _:
            raise RuntimeError("missing OPENAI_API_KEY")
        llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
        prompt = (pathlib.Path(__file__).parent / "prompts" / "skeptic.md").read_text()
        content = f"{prompt}\n\nDraft: {s.get('draft','')[:4000]}\n\nDocs: {json.dumps(s.get('docs', []))[:4000]}"
        res = llm.invoke(content)
        return {"critique": res.content}
    except Exception:
        return {"critique": "risk acceptable; check slippage; ensure evidence cites official source"}


def _compute_consensus(draft: dict, critique: str) -> float:
    # Simple heuristic consensus score for scaffold
    required_keys = ["symbol", "side", "size_bps_equity", "risk"]
    present = sum(1 for k in required_keys if k in draft)
    penalty = 0.0 if "invalid" not in critique.lower() else 0.5
    return max(0.0, min(1.0, present / len(required_keys) - penalty))


def node_referee(s: State):
    try:
        data = json.loads(s["draft"]) if isinstance(s.get("draft"), str) else s.get("draft", {})
    except Exception:
        raise RuntimeError("invalid draft JSON")
    # Compute consensus score from draft and critique
    consensus_score = _compute_consensus(data, s.get("critique", ""))
    min_consensus = float(os.getenv("CONSENSUS_MIN", "0.6"))
    data["consensus_score"] = consensus_score
    # Optional LLM refinement
    mode = os.getenv("AGENT_MODE", "deterministic").lower()
    if mode == "llm":
        try:
            _ = os.environ.get("OPENAI_API_KEY")
            if not _:
                raise RuntimeError("missing OPENAI_API_KEY")
            llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
            prompt = (pathlib.Path(__file__).parent / "prompts" / "referee.md").read_text()
            content = f"{prompt}\n\nDraft: {json.dumps(data)}\n\nCritique: {s.get('critique','')}\n\nDocs: {json.dumps(s.get('docs', []))[:4000]}"
            res = llm.invoke(content)
            try:
                data = json.loads(res.content)
            except Exception:
                pass
        except Exception:
            pass
    try:
        Proposal.model_validate(data)
    except ValidationError as e:
        raise RuntimeError(f"invalid proposal: {e}")
    # Must-cite: at least one evidence URL must be among collected docs
    try:
        docs = s.get("docs", [])
        doc_urls = {d.get("url") for d in docs if d.get("url")}
        ev_urls = {ev.get("url") for ev in (data.get("evidence") or []) if ev.get("url")}
        if not (doc_urls & ev_urls):
            raise RuntimeError("proposal lacks citations to retrieved docs")
    except Exception:
        raise RuntimeError("proposal lacks citations to retrieved docs")
    if consensus_score < min_consensus:
        raise RuntimeError("consensus too low")
    return {"proposal": data}


graph = StateGraph(State)
graph.add_node("reader", node_reader)
graph.add_node("proposer", node_proposer)
graph.add_node("skeptic", node_skeptic)
graph.add_node("referee", node_referee)
graph.set_entry_point("reader")
graph.add_edge("reader", "proposer")
graph.add_edge("proposer", "skeptic")
graph.add_edge("skeptic", "referee")
graph.add_edge("referee", END)
compiled = graph.compile()


