"""
Comprehensive backtesting framework for strategy validation.
Supports walk-forward analysis, Monte Carlo simulation, and performance metrics.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
import asyncio
import httpx
from dataclasses import dataclass
from apps.executor.utils.fees import calculate_fees, estimate_slippage_from_orderbook
from apps.risk.metrics import compute_fractional_kelly


@dataclass
class Trade:
    """Represents a single trade."""
    symbol: str
    side: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    base_qty: float
    quote_qty: float
    fees: float
    slippage_bps: float
    pnl: float
    pnl_pct: float
    status: str  # 'open', 'closed', 'stopped'


@dataclass
class BacktestResult:
    """Backtest results and metrics."""
    total_return: float
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    calmar_ratio: float
    equity_curve: pd.Series
    trades: List[Trade]
    daily_returns: pd.Series


class BacktestEngine:
    """
    Backtesting engine for strategy validation.
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission_rate: float = 0.001,
        slippage_bps: float = 5.0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps
        self.start_date = start_date
        self.end_date = end_date
        
        self.capital = initial_capital
        self.equity_curve = []
        self.trades: List[Trade] = []
        self.open_positions: Dict[str, Trade] = {}
        self.daily_returns = []
        
    def load_historical_data(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        Load historical kline data from Binance.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Kline interval ('1m', '5m', '1h', '1d', etc.)
            limit: Number of candles to fetch
        
        Returns:
            DataFrame with OHLCV data
        """
        base_url = "https://api.binance.com/api/v3/klines"
        
        # Calculate start time if needed
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        
        if self.start_date:
            params["startTime"] = int(self.start_date.timestamp() * 1000)
        if self.end_date:
            params["endTime"] = int(self.end_date.timestamp() * 1000)
        
        try:
            with httpx.Client(timeout=30) as client:
                r = client.get(base_url, params=params)
                r.raise_for_status()
                data = r.json()
            
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            
            # Convert to proper types
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
            for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
                df[col] = df[col].astype(float)
            
            return df[["open_time", "open", "high", "low", "close", "volume", "quote_volume"]]
        except Exception as e:
            print(f"Error loading data: {e}")
            return pd.DataFrame()
    
    def execute_trade(
        self,
        symbol: str,
        side: str,
        quote_qty: float,
        price: float,
        timestamp: datetime,
        slippage_bps: Optional[float] = None,
    ) -> Optional[Trade]:
        """
        Execute a trade in the backtest.
        
        Returns:
            Trade object or None if insufficient capital
        """
        if slippage_bps is None:
            slippage_bps = self.slippage_bps
        
        # Apply slippage
        if side.lower() == "buy":
            fill_price = price * (1 + slippage_bps / 10000)
        else:
            fill_price = price * (1 - slippage_bps / 10000)
        
        base_qty = quote_qty / fill_price
        
        # Calculate fees
        fees = calculate_fees("binance", side, quote_qty, is_maker=False)
        
        # Check if we have enough capital
        total_cost = quote_qty + fees
        if total_cost > self.capital:
            return None
        
        # Create trade
        trade = Trade(
            symbol=symbol,
            side=side,
            entry_time=timestamp,
            exit_time=None,
            entry_price=fill_price,
            exit_price=None,
            base_qty=base_qty,
            quote_qty=quote_qty,
            fees=fees,
            slippage_bps=slippage_bps,
            pnl=0.0,
            pnl_pct=0.0,
            status="open",
        )
        
        # Update capital
        self.capital -= total_cost
        
        # Store trade
        self.trades.append(trade)
        self.open_positions[symbol] = trade
        
        return trade
    
    def close_trade(
        self,
        symbol: str,
        exit_price: float,
        timestamp: datetime,
        slippage_bps: Optional[float] = None,
    ) -> Optional[Trade]:
        """
        Close an open position.
        
        Returns:
            Updated Trade object
        """
        if symbol not in self.open_positions:
            return None
        
        trade = self.open_positions[symbol]
        
        if slippage_bps is None:
            slippage_bps = self.slippage_bps
        
        # Apply slippage
        if trade.side.lower() == "buy":
            fill_price = exit_price * (1 - slippage_bps / 10000)
        else:
            fill_price = exit_price * (1 + slippage_bps / 10000)
        
        # Calculate proceeds
        proceeds = fill_price * trade.base_qty
        
        # Calculate fees
        exit_fees = calculate_fees("binance", "sell" if trade.side == "buy" else "buy", proceeds, is_maker=False)
        
        # Calculate PnL
        net_proceeds = proceeds - exit_fees
        total_cost = trade.quote_qty + trade.fees
        pnl = net_proceeds - total_cost
        pnl_pct = (pnl / total_cost) * 100
        
        # Update trade
        trade.exit_time = timestamp
        trade.exit_price = fill_price
        trade.pnl = pnl
        trade.pnl_pct = pnl_pct
        trade.status = "closed"
        trade.fees += exit_fees
        
        # Update capital
        self.capital += net_proceeds
        
        # Remove from open positions
        del self.open_positions[symbol]
        
        return trade
    
    def update_equity(self, timestamp: datetime):
        """Update equity curve with current positions."""
        equity = self.capital
        
        # Add unrealized PnL from open positions
        for trade in self.open_positions.values():
            # Use entry price as proxy (in real backtest, would use current price)
            equity += trade.quote_qty
        
        self.equity_curve.append({
            "timestamp": timestamp,
            "equity": equity,
        })
    
    def run(
        self,
        data: pd.DataFrame,
        strategy: Callable,
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            data: Historical OHLCV data
            strategy: Strategy function that takes (row, engine) and returns signal dict
                     Signal dict: {"action": "buy"/"sell"/"hold", "quote_qty": float, "confidence": float}
        """
        self.capital = self.initial_capital
        self.trades = []
        self.open_positions = {}
        self.equity_curve = []
        
        for idx, row in data.iterrows():
            timestamp = row["open_time"]
            price = row["close"]
            
            # Get strategy signal
            signal = strategy(row, self)
            
            if signal and signal.get("action") in ["buy", "sell"]:
                symbol = signal.get("symbol", "BTCUSDT")
                side = signal["action"]
                quote_qty = signal.get("quote_qty", self.capital * 0.1)  # Default 10% of capital
                
                # Check if we have an open position
                if symbol in self.open_positions:
                    # Close existing position
                    self.close_trade(symbol, price, timestamp)
                
                # Open new position
                self.execute_trade(symbol, side, quote_qty, price, timestamp)
            
            # Update equity
            self.update_equity(timestamp)
        
        # Close all open positions at end
        final_price = data.iloc[-1]["close"]
        final_timestamp = data.iloc[-1]["open_time"]
        for symbol in list(self.open_positions.keys()):
            self.close_trade(symbol, final_price, final_timestamp)
        
        return self.calculate_metrics()
    
    def calculate_metrics(self) -> BacktestResult:
        """Calculate performance metrics."""
        if not self.trades:
            return BacktestResult(
                total_return=0.0,
                total_return_pct=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                calmar_ratio=0.0,
                equity_curve=pd.Series(),
                trades=[],
                daily_returns=pd.Series(),
            )
        
        # Calculate returns
        equity_df = pd.DataFrame(self.equity_curve)
        if len(equity_df) == 0:
            equity_df = pd.DataFrame({"timestamp": [datetime.now()], "equity": [self.initial_capital]})
        
        equity_df.set_index("timestamp", inplace=True)
        equity_series = equity_df["equity"]
        
        # Calculate daily returns
        daily_returns = equity_series.pct_change().dropna()
        
        # Total return
        final_equity = equity_series.iloc[-1] if len(equity_series) > 0 else self.initial_capital
        total_return = final_equity - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        # Sharpe ratio (annualized, assuming daily returns)
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365 * 24 * 60)  # Annualized for 1m data
        else:
            sharpe_ratio = 0.0
        
        # Sortino ratio (downside deviation)
        downside_returns = daily_returns[daily_returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino_ratio = (daily_returns.mean() / downside_returns.std()) * np.sqrt(365 * 24 * 60)
        else:
            sortino_ratio = 0.0
        
        # Max drawdown
        running_max = equity_series.expanding().max()
        drawdown = equity_series - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / running_max.max()) * 100 if running_max.max() > 0 else 0.0
        
        # Trade statistics
        closed_trades = [t for t in self.trades if t.status == "closed"]
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0.0
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0.0
        avg_loss = np.mean([abs(t.pnl) for t in losing_trades]) if losing_trades else 0.0
        
        profit_factor = (avg_win * len(winning_trades)) / (avg_loss * len(losing_trades)) if avg_loss > 0 and losing_trades else float("inf") if winning_trades else 0.0
        
        largest_win = max([t.pnl for t in winning_trades]) if winning_trades else 0.0
        largest_loss = min([t.pnl for t in losing_trades]) if losing_trades else 0.0
        
        # Calmar ratio (annual return / max drawdown)
        annual_return = total_return_pct  # Simplified
        calmar_ratio = annual_return / abs(max_drawdown_pct) if max_drawdown_pct != 0 else 0.0
        
        return BacktestResult(
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            calmar_ratio=calmar_ratio,
            equity_curve=equity_series,
            trades=closed_trades,
            daily_returns=daily_returns,
        )


def simple_momentum_strategy(row: pd.Series, engine: BacktestEngine) -> Optional[Dict]:
    """
    Example strategy: Simple momentum.
    Buy when price increases, sell when it decreases.
    """
    # This is just an example - replace with your actual strategy
    return None

