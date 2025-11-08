from dataclasses import dataclass


@dataclass
class BanditDecision:
    status: str
    size_multiplier: float
    key: str


