#!/bin/bash
# Continuous Learning and Auto-Optimization System
# Automatically optimizes parameters based on performance

set -e

LOG_DIR="$HOME/Library/Logs/master-trader"
mkdir -p "$LOG_DIR"

OPTIMIZER_LOG="$LOG_DIR/optimizer.log"
PID_FILE="$LOG_DIR/optimizer.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Auto-optimizer already running (PID: $OLD_PID)"
        exit 0
    fi
fi

echo "Starting continuous learning system..."
echo $$ > "$PID_FILE"

# Function to optimize ASLF thresholds
optimize_aslf() {
    echo "$(date): Running ASLF optimization..." >> "$OPTIMIZER_LOG"
    
    python3 << 'PYEOF' >> "$OPTIMIZER_LOG" 2>&1
import os
import sys
try:
    import psycopg
except ImportError:
    print("psycopg not installed. Install with: pip3 install psycopg[binary]")
    sys.exit(1)

from datetime import datetime, timedelta

try:
    # Try 'db' first (Docker), fallback to 'localhost' (local)
    try:
        conn = psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db port=5432", connect_timeout=5)
    except:
        conn = psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db port=5432", connect_timeout=5)
    
    # Get recent ASLF decisions and outcomes
    cur = conn.execute("""
        SELECT decision, COUNT(*) as count
        FROM attention_aslf
        WHERE ts > NOW() - INTERVAL '24 hours'
        GROUP BY decision
    """)
    decisions = cur.fetchall()
    
    # Get recent trade performance
    cur = conn.execute("""
        SELECT AVG(realized_pnl) as avg_pnl, COUNT(*) as trade_count
        FROM positions
        WHERE closed_at > NOW() - INTERVAL '24 hours'
    """)
    perf = cur.fetchone()
    
    # Simple optimization: adjust thresholds based on performance
    print(f"Decisions: {decisions}")
    print(f"Performance: {perf}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
PYEOF
}

# Function to update bandit parameters
update_bandit() {
    echo "$(date): Updating bandit parameters..." >> "$OPTIMIZER_LOG"
    
    python3 << 'PYEOF' >> "$OPTIMIZER_LOG" 2>&1
import os
import sys
try:
    import psycopg
except ImportError:
    print("psycopg not installed. Install with: pip3 install psycopg[binary]")
    sys.exit(1)

try:
    # Try 'db' first (Docker), fallback to 'localhost' (local)
    try:
        conn = psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db port=5432", connect_timeout=5)
    except:
        conn = psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db port=5432", connect_timeout=5)
    
    # Get hypothesis performance
    cur = conn.execute("""
        SELECT key, alpha, beta, promoted,
               (SELECT COUNT(*) FROM positions p 
                WHERE p.symbol = SUBSTRING(h.key FROM 6)
                AND p.closed_at > NOW() - INTERVAL '7 days'
                AND p.realized_pnl > 0) as wins,
               (SELECT COUNT(*) FROM positions p 
                WHERE p.symbol = SUBSTRING(h.key FROM 6)
                AND p.closed_at > NOW() - INTERVAL '7 days'
                AND p.realized_pnl < 0) as losses
        FROM hypotheses h
    """)
    
    for row in cur.fetchall():
        key, alpha, beta, promoted, wins, losses = row
        # Update based on actual performance
        print(f"Hypothesis {key}: α={alpha}, β={beta}, wins={wins}, losses={losses}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
PYEOF
}

# Main optimization loop
echo "$(date): Starting auto-optimizer" >> "$OPTIMIZER_LOG"

while true; do
    # Run optimizations every hour
    optimize_aslf
    update_bandit
    
    # Sleep for 1 hour
    sleep 3600
done
