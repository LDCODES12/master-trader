-- Position tracking system for open positions and PnL calculation

CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    side TEXT CHECK (side IN ('buy', 'sell')) NOT NULL,
    base_qty NUMERIC NOT NULL,
    quote_qty NUMERIC NOT NULL,
    entry_price NUMERIC NOT NULL,
    current_price NUMERIC,
    unrealized_pnl NUMERIC DEFAULT 0,
    realized_pnl NUMERIC DEFAULT 0,
    fees_paid NUMERIC DEFAULT 0,
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    execution_id UUID REFERENCES executions(id),
    venue TEXT,
    notes TEXT,
    -- Prevent duplicate open positions (can have multiple closes)
    CONSTRAINT unique_open_position UNIQUE NULLS NOT DISTINCT (symbol, side, opened_at, closed_at)
);

CREATE INDEX IF NOT EXISTS idx_positions_open ON positions(closed_at) WHERE closed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_execution ON positions(execution_id);

-- Portfolio exposure tracking
CREATE TABLE IF NOT EXISTS portfolio_exposure (
    ts TIMESTAMPTZ DEFAULT NOW(),
    total_exposure NUMERIC NOT NULL,
    long_exposure NUMERIC NOT NULL,
    short_exposure NUMERIC NOT NULL,
    net_exposure NUMERIC NOT NULL,
    leverage NUMERIC,
    symbols_count INT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_portfolio_exposure_ts ON portfolio_exposure(ts DESC);

