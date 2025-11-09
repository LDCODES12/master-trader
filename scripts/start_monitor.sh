#!/bin/bash
# 24/7 Health Monitoring and Auto-Recovery System
# Runs continuously to ensure system stays online

set -e

LOG_DIR="$HOME/Library/Logs/master-trader"
mkdir -p "$LOG_DIR"

MONITOR_LOG="$LOG_DIR/monitor.log"
PID_FILE="$LOG_DIR/monitor.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Monitor already running (PID: $OLD_PID)"
        exit 0
    fi
fi

echo "Starting 24/7 health monitor..."
echo $$ > "$PID_FILE"

# Function to check service health
check_service() {
    local service=$1
    local url=$2
    
    if curl -s --max-time 5 "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to restart service
restart_service() {
    local service=$1
    echo "$(date): Restarting $service" >> "$MONITOR_LOG"
    docker compose -f infra/docker-compose.yml restart "$service" >> "$MONITOR_LOG" 2>&1
}

# Function to check and restart if needed
ensure_service() {
    local service=$1
    local url=$2
    
    if ! check_service "$service" "$url"; then
        echo "$(date): $service is down, restarting..." >> "$MONITOR_LOG"
        restart_service "$service"
        sleep 10
        
        # Verify restart
        RETRIES=0
        while [ $RETRIES -lt 5 ]; do
            if check_service "$service" "$url"; then
                echo "$(date): $service recovered" >> "$MONITOR_LOG"
                return 0
            fi
            RETRIES=$((RETRIES + 1))
            sleep 5
        done
        
        echo "$(date): ERROR: $service failed to recover" >> "$MONITOR_LOG"
        # Send alert (can be extended with email/Slack/etc)
        return 1
    fi
}

# Main monitoring loop
echo "$(date): Starting health monitor" >> "$MONITOR_LOG"

while true; do
    # Check gateway
    ensure_service "gateway" "http://localhost:8000/status"
    
    # Check executor
    ensure_service "executor" "http://localhost:8001/status"
    
    # Check temporal
    ensure_service "temporal" "http://localhost:7233"
    
    # Check database connectivity
    if ! docker compose -f infra/docker-compose.yml exec -T db pg_isready -U trader > /dev/null 2>&1; then
        echo "$(date): Database not ready, restarting..." >> "$MONITOR_LOG"
        restart_service "db"
    fi
    
    # Check disk space
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -gt 90 ]; then
        echo "$(date): WARNING: Disk usage at ${DISK_USAGE}%" >> "$MONITOR_LOG"
    fi
    
    # Sleep before next check
    sleep 30
done

