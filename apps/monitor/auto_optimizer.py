"""
Continuous learning and auto-optimization system.
Automatically adjusts parameters based on performance.
"""

import os
import psycopg
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import json


class AutoOptimizer:
    """Automatically optimizes trading parameters based on performance."""
    
    def __init__(self):
        self.db_dsn = os.getenv("PG_DSN", "postgresql://trader:traderpw@db:5432/mastertrader")
        self.optimization_interval = int(os.getenv("OPTIMIZATION_INTERVAL_S", "3600"))  # 1 hour
    
    def get_recent_performance(self, hours: int = 24) -> Dict:
        """Get recent trading performance metrics."""
        with psycopg.connect(self.db_dsn) as conn:
            # Get closed positions from last N hours
            cur = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    AVG(realized_pnl) as avg_pnl,
                    SUM(realized_pnl) as total_pnl,
                    AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE NULL END) as avg_win,
                    AVG(CASE WHEN realized_pnl < 0 THEN ABS(realized_pnl) ELSE NULL END) as avg_loss
                FROM positions
                WHERE closed_at > NOW() - INTERVAL '%s hours'
                """,
                (hours,),
            )
            row = cur.fetchone()
            
            if row and row[0]:
                return {
                    "total_trades": row[0],
                    "winning_trades": row[1] or 0,
                    "losing_trades": row[2] or 0,
                    "win_rate": (row[1] or 0) / row[0] if row[0] > 0 else 0,
                    "avg_pnl": float(row[3] or 0),
                    "total_pnl": float(row[4] or 0),
                    "avg_win": float(row[5] or 0),
                    "avg_loss": float(row[6] or 0),
                    "profit_factor": (float(row[5] or 0) * (row[1] or 0)) / (float(row[6] or 0) * (row[2] or 1)) if row[2] and row[6] else 0,
                }
        
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "avg_pnl": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
        }
    
    def get_aslf_performance(self) -> Dict:
        """Analyze ASLF decision performance."""
        with psycopg.connect(self.db_dsn) as conn:
            # Get ASLF decisions and correlate with outcomes
            cur = conn.execute(
                """
                SELECT 
                    aas.decision,
                    COUNT(*) as decision_count,
                    AVG(p.realized_pnl) as avg_pnl,
                    SUM(CASE WHEN p.realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN p.realized_pnl < 0 THEN 1 ELSE 0 END) as losses
                FROM attention_aslf aas
                LEFT JOIN positions p ON p.symbol = aas.symbol 
                    AND p.opened_at BETWEEN aas.ts AND aas.ts + INTERVAL '1 hour'
                WHERE aas.ts > NOW() - INTERVAL '24 hours'
                GROUP BY aas.decision
                """
            )
            
            results = {}
            for row in cur.fetchall():
                decision, count, avg_pnl, wins, losses = row
                results[decision] = {
                    "count": count,
                    "avg_pnl": float(avg_pnl or 0),
                    "wins": wins or 0,
                    "losses": losses or 0,
                    "win_rate": (wins or 0) / max(1, (wins or 0) + (losses or 0)),
                }
            
            return results
    
    def optimize_aslf_thresholds(self) -> Optional[Dict]:
        """Optimize ASLF thresholds based on performance."""
        perf = self.get_aslf_performance()
        recent_perf = self.get_recent_performance(24)
        
        # If we're denying too many profitable trades, lower threshold
        # If we're allowing too many unprofitable trades, raise threshold
        
        allow_perf = perf.get("allow", {})
        deny_perf = perf.get("deny", {})
        
        current_theta_buy = float(os.getenv("ASLF_THETA_BUY", "0.8"))
        
        # Simple optimization logic
        if allow_perf.get("win_rate", 0) > 0.6 and recent_perf["win_rate"] > 0.55:
            # Good performance, can be more aggressive
            new_theta = max(0.5, current_theta_buy - 0.1)
            print(f"Optimizing ASLF_THETA_BUY: {current_theta_buy} -> {new_theta} (more aggressive)")
            return {"ASLF_THETA_BUY": new_theta}
        elif allow_perf.get("win_rate", 0) < 0.5:
            # Poor performance, be more conservative
            new_theta = min(1.5, current_theta_buy + 0.1)
            print(f"Optimizing ASLF_THETA_BUY: {current_theta_buy} -> {new_theta} (more conservative)")
            return {"ASLF_THETA_BUY": new_theta}
        
        return None
    
    def optimize_bandit_parameters(self) -> None:
        """Update bandit parameters based on actual outcomes."""
        with psycopg.connect(self.db_dsn) as conn:
            # Get all hypotheses
            cur = conn.execute("SELECT key, alpha, beta, promoted FROM hypotheses")
            
            for row in cur.fetchall():
                key, alpha, beta, promoted = row
                symbol = key.replace("aslf:", "")
                
                # Get actual performance for this symbol
                perf_cur = conn.execute(
                    """
                    SELECT 
                        SUM(CASE WHEN realized_pnl > 0 THEN 1.0 ELSE 0.0 END) as wins,
                        SUM(CASE WHEN realized_pnl < 0 THEN 1.0 ELSE 0.0 END) as losses,
                        AVG(realized_pnl) as avg_pnl
                    FROM positions
                    WHERE symbol = %s AND closed_at > NOW() - INTERVAL '7 days'
                    """,
                    (symbol,),
                )
                perf_row = perf_cur.fetchone()
                
                if perf_row and (perf_row[0] or perf_row[1]):
                    wins = float(perf_row[0] or 0)
                    losses = float(perf_row[1] or 0)
                    
                    # Update alpha/beta based on actual outcomes
                    # Simple: add wins to alpha, losses to beta
                    new_alpha = float(alpha) + wins
                    new_beta = float(beta) + losses
                    
                    # Update promotion status
                    p_mean = new_alpha / max(1.0, new_alpha + new_beta)
                    new_promoted = promoted or (p_mean >= 0.7)
                    
                    conn.execute(
                        "UPDATE hypotheses SET alpha = %s, beta = %s, promoted = %s, updated_at = NOW() WHERE key = %s",
                        (new_alpha, new_beta, new_promoted, key),
                    )
                    conn.commit()
                    
                    print(f"Updated {key}: α={new_alpha:.2f}, β={new_beta:.2f}, promoted={new_promoted}")
    
    def optimize_position_sizing(self) -> Optional[Dict]:
        """Optimize position sizing based on performance."""
        recent_perf = self.get_recent_performance(24)
        
        current_max_size = float(os.getenv("MAX_POSITION_SIZE_PCT", "20.0"))
        
        # If win rate is high and profit factor is good, can increase size
        if recent_perf["win_rate"] > 0.6 and recent_perf["profit_factor"] > 1.5:
            new_size = min(25.0, current_max_size + 2.0)
            print(f"Optimizing MAX_POSITION_SIZE_PCT: {current_max_size} -> {new_size}")
            return {"MAX_POSITION_SIZE_PCT": new_size}
        elif recent_perf["win_rate"] < 0.5:
            # Reduce size if performance is poor
            new_size = max(10.0, current_max_size - 2.0)
            print(f"Optimizing MAX_POSITION_SIZE_PCT: {current_max_size} -> {new_size}")
            return {"MAX_POSITION_SIZE_PCT": new_size}
        
        return None
    
    async def run_optimization_cycle(self):
        """Run one optimization cycle."""
        print(f"[{datetime.now()}] Running optimization cycle...")
        
        # Optimize ASLF thresholds
        aslf_opts = self.optimize_aslf_thresholds()
        if aslf_opts:
            # In production, would update environment or config
            print(f"ASLF optimizations: {aslf_opts}")
        
        # Update bandit parameters
        self.optimize_bandit_parameters()
        
        # Optimize position sizing
        size_opts = self.optimize_position_sizing()
        if size_opts:
            print(f"Position sizing optimizations: {size_opts}")
        
        print(f"[{datetime.now()}] Optimization cycle complete")
    
    async def run_continuous(self):
        """Run continuous optimization loop."""
        print(f"[{datetime.now()}] Starting continuous optimizer (interval: {self.optimization_interval}s)")
        
        while True:
            try:
                await self.run_optimization_cycle()
            except Exception as e:
                print(f"Error in optimization cycle: {e}")
            
            await asyncio.sleep(self.optimization_interval)


if __name__ == "__main__":
    optimizer = AutoOptimizer()
    asyncio.run(optimizer.run_continuous())

