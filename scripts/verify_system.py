#!/usr/bin/env python3
"""Verify the entire system is working end-to-end."""
import asyncio
import httpx
import os
from temporalio.client import Client

async def test_temporal_connection():
    """Test Temporal connection."""
    try:
        client = await Client.connect("localhost:7233")
        print("✅ Temporal connection: OK")
        await client.close()
        return True
    except Exception as e:
        print(f"❌ Temporal connection failed: {e}")
        return False

async def test_gateway():
    """Test gateway endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("http://localhost:8000/status")
            if r.status_code == 200:
                print("✅ Gateway: OK")
                return True
    except Exception as e:
        print(f"❌ Gateway failed: {e}")
    return False

async def test_workflow_submission():
    """Submit a test workflow and check if it processes."""
    proposal = {
        "action": "open",
        "symbol": "BTCUSDT",
        "side": "buy",
        "size_bps_equity": 4.0,
        "horizon_minutes": 120,
        "thesis": "System verification test",
        "risk": {
            "stop_loss_bps": 60,
            "take_profit_bps": 120,
            "max_slippage_bps": 3
        },
        "evidence": [{
            "url": "https://www.binance.com/en/support/announcement",
            "type": "exchange_status"
        }],
        "confidence": 0.7
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "http://localhost:8000/submit-proposal",
                json={"proposal": proposal},
                headers={"Idempotency-Key": f"verify-{os.getpid()}"}
            )
            if r.status_code == 200:
                result = r.json()
                print(f"✅ Workflow submitted: {result.get('workflow_id')}")
                return result.get('workflow_id')
    except Exception as e:
        print(f"❌ Workflow submission failed: {e}")
    return None

async def check_workflow_status(workflow_id):
    """Check if workflow is running."""
    try:
        client = await Client.connect("localhost:7233")
        handle = client.get_workflow_handle(workflow_id)
        result = await handle.result(timeout=60)
        print(f"✅ Workflow completed: {result}")
        await client.close()
        return True
    except Exception as e:
        print(f"⚠️  Workflow status check: {e}")
        return False

async def main():
    print("🔍 Verifying system...")
    print()
    
    # Test connections
    temporal_ok = await test_temporal_connection()
    gateway_ok = await test_gateway()
    
    if not temporal_ok or not gateway_ok:
        print("\n❌ Basic connections failed. Check services.")
        return
    
    # Submit workflow
    print("\n📤 Submitting test workflow...")
    workflow_id = await test_workflow_submission()
    
    if workflow_id:
        print(f"\n⏳ Waiting for workflow to process...")
        await asyncio.sleep(10)
        await check_workflow_status(workflow_id)
    
    print("\n✅ Verification complete!")

if __name__ == "__main__":
    asyncio.run(main())

