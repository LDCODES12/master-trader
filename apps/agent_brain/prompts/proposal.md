Produce a strict JSON matching the `Proposal` schema fields exactly.
No extra keys. Validate ranges and types.

Fields:
- action: "open" | "reduce" | "close"
- symbol: string (e.g., BTCUSDT)
- side: "buy" | "sell"
- size_bps_equity: float
- horizon_minutes: int
- thesis: string (concise rationale)
- risk: { stop_loss_bps, take_profit_bps, max_slippage_bps }
- evidence: list of { url, type }
- confidence: float in [0.0, 1.0]


