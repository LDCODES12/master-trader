#!/usr/bin/env python3
"""
Test proposal submission script for Phase 1 validation.
"""

import httpx
import os
import sys
from datetime import datetime

# Configuration
GATEWAY_URL = os.getenv("GATEWAY_URL", "https://master-trader.onrender.com")
# For local testing, use: http://localhost:8000

def submit_test_proposal():
    """Submit a test trade proposal."""
    
    proposal = {
        "action": "open",
        "symbol": "BTCUSDT",
        "side": "buy",
        "size_bps_equity": 4.0,  # 4% of equity
        "horizon_minutes": 120,  # 2 hour horizon
        "thesis": "Phase 1 test - validating system end-to-end",
        "risk": {
            "stop_loss_bps": 60,      # 0.6% stop loss
            "take_profit_bps": 120,   # 1.2% take profit
            "max_slippage_bps": 3     # 0.03% max slippage
        },
        "evidence": [
            {
                "url": "https://www.binance.com/en/support/announcement",
                "type": "exchange_status"
            }
        ],
        "confidence": 0.7
    }
    
    # Generate unique idempotency key
    idempotency_key = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    print(f"🚀 Submitting test proposal to {GATEWAY_URL}")
    print(f"   Symbol: {proposal['symbol']}")
    print(f"   Side: {proposal['side']}")
    print(f"   Size: {proposal['size_bps_equity']}% of equity")
    print(f"   Idempotency Key: {idempotency_key}")
    print()
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{GATEWAY_URL}/submit-proposal",
                json={"proposal": proposal},
                headers={
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Proposal accepted!")
                print(f"   Workflow ID: {result.get('workflow_id', 'N/A')}")
                print()
                print("📊 Next steps:")
                print("   1. Check Render logs for workflow execution")
                print("   2. Verify paper trade was executed")
                print("   3. Check database for position tracking")
                return True
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
    except httpx.ConnectError:
        print(f"❌ Connection error: Could not reach {GATEWAY_URL}")
        print("   Make sure the service is running and accessible")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = submit_test_proposal()
    sys.exit(0 if success else 1)

