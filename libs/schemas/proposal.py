from pydantic import BaseModel, Field, HttpUrl
from typing import List, Literal


class Evidence(BaseModel):
    url: HttpUrl
    type: Literal["news_headline", "onchain_alert", "exchange_status"]


class RiskParams(BaseModel):
    stop_loss_bps: int
    take_profit_bps: int
    max_slippage_bps: int


class Proposal(BaseModel):
    action: Literal["open", "reduce", "close"]
    symbol: str
    side: Literal["buy", "sell"]
    size_bps_equity: float
    horizon_minutes: int
    thesis: str
    risk: RiskParams
    evidence: List[Evidence]
    confidence: float = Field(ge=0.0, le=1.0)


