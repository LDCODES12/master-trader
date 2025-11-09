"""
Comprehensive health monitoring system.
Checks all services, database, and trading health.
"""

import os
import time
import httpx
import psycopg
from typing import Dict, List, Optional
from datetime import datetime


class HealthMonitor:
    """Monitors system health and triggers alerts/recovery."""
    
    def __init__(self):
        self.gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
        self.executor_url = os.getenv("EXECUTOR_URL", "http://localhost:8001")
        self.temporal_url = os.getenv("TEMPORAL_URL", "http://localhost:7233")
        self.db_dsn = os.getenv("PG_DSN", "postgresql://trader:traderpw@db:5432/mastertrader")
    
    def check_gateway(self) -> Dict:
        """Check gateway service health."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.gateway_url}/status")
                if r.status_code == 200:
                    return {"status": "healthy", "response_time_ms": r.elapsed.total_seconds() * 1000}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
        return {"status": "unhealthy", "error": "unknown"}
    
    def check_executor(self) -> Dict:
        """Check executor service health."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.executor_url}/status")
                if r.status_code == 200:
                    return {"status": "healthy", "response_time_ms": r.elapsed.total_seconds() * 1000}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
        return {"status": "unhealthy", "error": "unknown"}
    
    def check_temporal(self) -> Dict:
        """Check Temporal service health."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.temporal_url}")
                return {"status": "healthy" if r.status_code < 500 else "unhealthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def check_database(self) -> Dict:
        """Check database connectivity and health."""
        try:
            with psycopg.connect(self.db_dsn, connect_timeout=5) as conn:
                cur = conn.execute("SELECT 1")
                cur.fetchone()
                return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def check_trading_health(self) -> Dict:
        """Check trading system health."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Check preflight
                r = await client.get(f"{self.gateway_url}/preflight")
                preflight = r.json() if r.status_code == 200 else {}
                
                # Check metrics
                r = await client.get(f"{self.gateway_url}/metrics")
                metrics = r.json() if r.status_code == 200 else {}
                
                return {
                    "status": "healthy" if metrics.get("green_to_trade", False) else "degraded",
                    "preflight": preflight,
                    "metrics": metrics,
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def check_positions(self) -> Dict:
        """Check position tracking health."""
        try:
            from apps.analytics.positions import get_open_positions, get_portfolio_exposure
            
            positions = get_open_positions()
            exposure = get_portfolio_exposure()
            
            return {
                "status": "healthy",
                "open_positions": len(positions),
                "total_exposure": exposure.get("total_exposure", 0),
                "leverage": exposure.get("leverage", 0),
                "unrealized_pnl": exposure.get("unrealized_pnl", 0),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def full_health_check(self) -> Dict:
        """Run complete health check."""
        return {
            "timestamp": datetime.now().isoformat(),
            "gateway": self.check_gateway(),
            "executor": self.check_executor(),
            "temporal": self.check_temporal(),
            "database": self.check_database(),
            "trading": self.check_trading_health(),
            "positions": self.check_positions(),
            "overall_status": "healthy",  # Will be updated based on checks
        }
    
    def should_restart_service(self, service_name: str, health: Dict) -> bool:
        """Determine if service should be restarted."""
        if health.get("status") != "healthy":
            # Check if it's been unhealthy for > 2 minutes
            # (In real implementation, track timestamps)
            return True
        return False


async def auto_recover():
    """Automatically recover unhealthy services."""
    monitor = HealthMonitor()
    health = monitor.full_health_check()
    
    # Check each service and restart if needed
    if monitor.should_restart_service("gateway", health["gateway"]):
        print("Restarting gateway...")
        # In production, would use docker compose API or similar
        os.system("docker compose -f infra/docker-compose.yml restart gateway")
    
    if monitor.should_restart_service("executor", health["executor"]):
        print("Restarting executor...")
        os.system("docker compose -f infra/docker-compose.yml restart executor")
    
    if monitor.should_restart_service("database", health["database"]):
        print("Restarting database...")
        os.system("docker compose -f infra/docker-compose.yml restart db")


if __name__ == "__main__":
    import asyncio
    monitor = HealthMonitor()
    health = monitor.full_health_check()
    print(health)

