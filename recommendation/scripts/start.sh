#!/bin/bash
# Recommendation Service Startup Script

set -e

echo "Starting Recommendation Service..."

# Configuration validation
validate_config() {
    echo "Validating configuration..."
    
    # Check required environment variables
    required_vars=(
        "REDIS_HOST"
        "REDIS_PORT"
        "GIN_MODE"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "ERROR: Required environment variable $var is not set"
            exit 1
        fi
    done
    
    # Validate Redis port is numeric
    if ! [[ "$REDIS_PORT" =~ ^[0-9]+$ ]]; then
        echo "ERROR: REDIS_PORT must be a number"
        exit 1
    fi
    
    echo "Configuration validation passed"
}

# Wait for Redis availability
wait_for_redis() {
    echo "Waiting for Redis to be available..."
    
    # Wait for Redis with timeout
    timeout 60 bash -c "
        until redis-cli -h $REDIS_HOST -p $REDIS_PORT ping > /dev/null 2>&1; do
            echo 'Waiting for Redis...'
            sleep 2
        done
    "
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Redis did not become available within timeout"
        exit 1
    fi
    
    echo "Redis is available"
}

# Graceful shutdown handler
shutdown_handler() {
    echo "Received shutdown signal, gracefully shutting down..."
    
    # Kill the main process if it's running
    if [ ! -z "$MAIN_PID" ]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        wait "$MAIN_PID" 2>/dev/null || true
    fi
    
    echo "Recommendation service stopped"
    exit 0
}

# Set up signal handlers
trap shutdown_handler SIGTERM SIGINT

# Run startup sequence
validate_config
wait_for_redis

echo "Starting Go application..."

# Start the main application
./recommendation_app &
MAIN_PID=$!

# Wait for the main process
wait "$MAIN_PID"