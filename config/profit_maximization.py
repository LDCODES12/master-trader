"""
Aggressive profit maximization configuration.
These settings prioritize maximum returns while maintaining risk controls.
"""

import os

# ============================================================================
# POSITION SIZING - AGGRESSIVE SETTINGS
# ============================================================================

# Maximum position size as % of equity (aggressive: 20% per position)
MAX_POSITION_SIZE_PCT = float(os.getenv("MAX_POSITION_SIZE_PCT", "20.0"))

# Maximum portfolio exposure as % of equity (aggressive: 300% = 3x leverage)
MAX_PORTFOLIO_EXPOSURE_PCT = float(os.getenv("MAX_PORTFOLIO_EXPOSURE_PCT", "300.0"))

# Fractional Kelly cap (aggressive: 0.5 = half Kelly, can go up to 1.0 for maximum)
FRACTIONAL_KELLY_MAX = float(os.getenv("FRACTIONAL_KELLY_MAX", "0.5"))

# Minimum confidence to trade (lower = more trades, higher = only best setups)
MIN_CONFIDENCE_THRESHOLD = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.6"))

# ============================================================================
# ASLF THRESHOLDS - AGGRESSIVE (LOWER BARRIER TO ENTRY)
# ============================================================================

# ASLF buy threshold (lower = more trades allowed)
ASLF_THETA_BUY = float(os.getenv("ASLF_THETA_BUY", "0.8"))  # Lowered from 1.2

# ASLF fade threshold (more aggressive shorting)
ASLF_THETA_FADE = float(os.getenv("ASLF_THETA_FADE", "-0.8"))  # More aggressive

# ASLF lambda (attention vs liquidity weight)
ASLF_LAMBDA = float(os.getenv("ASLF_LAMBDA", "0.4"))  # Lower = more attention weight

# ============================================================================
# RISK PARAMETERS - BALANCED FOR PROFIT MAXIMIZATION
# ============================================================================

# Maximum drawdown limit (aggressive: 25% before circuit breaker)
MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", "25.0"))

# Daily loss limit as % of equity (aggressive: 10% per day)
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "10.0"))

# Stop loss default (tighter for faster exits, wider for more room)
DEFAULT_STOP_LOSS_BPS = int(os.getenv("DEFAULT_STOP_LOSS_BPS", "80"))

# Take profit default (aim for 2-3x risk)
DEFAULT_TAKE_PROFIT_BPS = int(os.getenv("DEFAULT_TAKE_PROFIT_BPS", "200"))

# ============================================================================
# EXECUTION - OPTIMIZED FOR COST MINIMIZATION
# ============================================================================

# Maximum acceptable slippage in bps (lower = better execution)
MAX_SLIPPAGE_BPS = float(os.getenv("MAX_SLIPPAGE_BPS", "10.0"))

# Impact threshold for slicing (lower = more slicing)
IMPACT_MAX_SLIPPAGE_BPS = float(os.getenv("IMPACT_MAX_SLIPPAGE_BPS", "10.0"))

# Enable smart order routing (saves 10-30% on costs)
ENABLE_SMART_ROUTING = os.getenv("ENABLE_SMART_ROUTING", "true").lower() == "true"

# ============================================================================
# BANDIT LEARNING - AGGRESSIVE PROMOTION
# ============================================================================

# Probability threshold for promotion (lower = faster promotion)
PROMOTE_PROB_THRESHOLD = float(os.getenv("PROMOTE_PROB_THRESHOLD", "0.7"))  # Lowered from 0.8

# Probe size in bps (smaller probes = faster learning)
PROBE_SIZE_BPS = float(os.getenv("PROBE_SIZE_BPS", "2.0"))  # Lowered from 3.0

# ============================================================================
# CONSENSUS THRESHOLD - AGGRESSIVE (LOWER BARRIER)
# ============================================================================

# Minimum consensus score (lower = more proposals pass)
CONSENSUS_MIN = float(os.getenv("CONSENSUS_MIN", "0.55"))  # Lowered from 0.6

# ============================================================================
# PROFIT TARGETS - AGGRESSIVE
# ============================================================================

# Target monthly return (aggressive: 15-20%)
TARGET_MONTHLY_RETURN_PCT = float(os.getenv("TARGET_MONTHLY_RETURN_PCT", "15.0"))

# Target Sharpe ratio (excellent: >2.0)
TARGET_SHARPE_RATIO = float(os.getenv("TARGET_SHARPE_RATIO", "2.0"))

# Minimum win rate target
MIN_WIN_RATE = float(os.getenv("MIN_WIN_RATE", "0.55"))

# ============================================================================
# TRADING ENABLED FLAGS
# ============================================================================

# Enable trading (set to false to pause)
TRADING_ENABLED = os.getenv("TRADING_ENABLED", "true").lower() == "true"

# Execution mode: dry_run, paper, live
EXEC_MODE = os.getenv("EXEC_MODE", "paper").lower()

# ============================================================================
# AGENT MODE - LLM FOR MAXIMUM SIGNAL QUALITY
# ============================================================================

# Agent mode: deterministic (stub) or llm (real AI)
AGENT_MODE = os.getenv("AGENT_MODE", "llm").lower()

# OpenAI model for agents
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ============================================================================
# SUMMARY
# ============================================================================

PROFIT_MAXIMIZATION_CONFIG = {
    "position_sizing": {
        "max_position_pct": MAX_POSITION_SIZE_PCT,
        "max_exposure_pct": MAX_PORTFOLIO_EXPOSURE_PCT,
        "kelly_cap": FRACTIONAL_KELLY_MAX,
        "min_confidence": MIN_CONFIDENCE_THRESHOLD,
    },
    "aslf": {
        "theta_buy": ASLF_THETA_BUY,
        "theta_fade": ASLF_THETA_FADE,
        "lambda": ASLF_LAMBDA,
    },
    "risk": {
        "max_drawdown_pct": MAX_DRAWDOWN_PCT,
        "max_daily_loss_pct": MAX_DAILY_LOSS_PCT,
        "default_stop_loss_bps": DEFAULT_STOP_LOSS_BPS,
        "default_take_profit_bps": DEFAULT_TAKE_PROFIT_BPS,
    },
    "execution": {
        "max_slippage_bps": MAX_SLIPPAGE_BPS,
        "impact_threshold_bps": IMPACT_MAX_SLIPPAGE_BPS,
        "smart_routing": ENABLE_SMART_ROUTING,
    },
    "bandit": {
        "promote_threshold": PROMOTE_PROB_THRESHOLD,
        "probe_size_bps": PROBE_SIZE_BPS,
    },
    "targets": {
        "monthly_return_pct": TARGET_MONTHLY_RETURN_PCT,
        "sharpe_ratio": TARGET_SHARPE_RATIO,
        "win_rate": MIN_WIN_RATE,
    },
    "mode": {
        "trading_enabled": TRADING_ENABLED,
        "exec_mode": EXEC_MODE,
        "agent_mode": AGENT_MODE,
    },
}

