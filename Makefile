SHELL := /bin/bash

.PHONY: bootstrap redeploy logs auto-setup status monitor stop-monitor optimize stop-optimize logs-all restart-all start stop full-restart

bootstrap:
	@echo "Use 'make start' instead"
	@make start

redeploy:
	@gh workflow run deploy-gcp.yml || gh workflow run .github/workflows/deploy-gcp.yml
	@sleep 3
	@gh run watch --exit-status || true

logs:
	@# If a remote logs workflow exists, run it; otherwise show latest run logs.
	@gh workflow run remote-logs.yml || true
	@sleep 2 || true
	@gh run watch --exit-status || true
	@gh run view --log || true

# ============================================================================
# FULLY AUTOMATED 24/7 OPERATION
# ============================================================================

auto-setup:
	@echo "🚀 Fully Automated Setup - Cursor handles everything"
	@chmod +x scripts/auto_setup.sh scripts/start_monitor.sh scripts/start_auto_optimizer.sh
	@./scripts/auto_setup.sh

status:
	@echo "=== System Status ==="
	@echo "Gateway:"
	@curl -s http://localhost:8000/status || echo "❌ Down"
	@echo ""
	@echo "Executor:"
	@curl -s http://localhost:8001/status || echo "❌ Down"
	@echo ""
	@echo "Metrics:"
	@curl -s http://localhost:8000/metrics | python3 -m json.tool 2>/dev/null || echo "❌ Unable to fetch"
	@echo ""
	@echo "Health Check:"
	@python3 -c "from apps.monitor.health import HealthMonitor; import asyncio; import json; print(json.dumps(asyncio.run(HealthMonitor().full_health_check()), indent=2))" 2>/dev/null || echo "❌ Health check failed"

monitor:
	@echo "Starting 24/7 health monitor..."
	@chmod +x scripts/start_monitor.sh
	@nohup bash scripts/start_monitor.sh > /dev/null 2>&1 &
	@echo "✅ Monitor started (PID: $$!)"
	@echo "Logs: tail -f $$HOME/Library/Logs/master-trader/monitor.log"

stop-monitor:
	@if [ -f $$HOME/Library/Logs/master-trader/monitor.pid ]; then \
		kill $$(cat $$HOME/Library/Logs/master-trader/monitor.pid) 2>/dev/null && echo "✅ Monitor stopped" || echo "Monitor not running"; \
		rm -f $$HOME/Library/Logs/master-trader/monitor.pid; \
	else \
		echo "Monitor not running"; \
	fi

optimize:
	@echo "Starting continuous learning system..."
	@chmod +x scripts/start_auto_optimizer.sh
	@nohup bash scripts/start_auto_optimizer.sh > /dev/null 2>&1 &
	@echo "✅ Optimizer started (PID: $$!)"
	@echo "Logs: tail -f $$HOME/Library/Logs/master-trader/optimizer.log"

stop-optimize:
	@if [ -f $$HOME/Library/Logs/master-trader/optimizer.pid ]; then \
		kill $$(cat $$HOME/Library/Logs/master-trader/optimizer.pid) 2>/dev/null && echo "✅ Optimizer stopped" || echo "Optimizer not running"; \
		rm -f $$HOME/Library/Logs/master-trader/optimizer.pid; \
	else \
		echo "Optimizer not running"; \
	fi

logs-all:
	@echo "=== All Logs ==="
	@echo "Monitor:"
	@tail -20 $$HOME/Library/Logs/master-trader/monitor.log 2>/dev/null || echo "No monitor logs"
	@echo ""
	@echo "Optimizer:"
	@tail -20 $$HOME/Library/Logs/master-trader/optimizer.log 2>/dev/null || echo "No optimizer logs"
	@echo ""
	@echo "Docker Services:"
	@docker compose -f infra/docker-compose.yml logs --tail=20

restart-all:
	@echo "Restarting all services..."
	@docker compose -f infra/docker-compose.yml restart
	@sleep 5
	@make status

# ============================================================================
# QUICK COMMANDS
# ============================================================================

start:
	@echo "🚀 Starting MasterTrader - Fully Automated 24/7 System"
	@chmod +x start.sh
	@./start.sh


stop: stop-monitor stop-optimize
	@echo "⚠️  Monitoring stopped. Services still running."

full-restart: stop restart-all start
	@echo "✅ Full restart complete!"
