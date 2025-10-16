#!/bin/bash
# Frontend Service Startup Script

set -e

echo "Starting Frontend Service..."

# Configuration validation
validate_config() {
    echo "Validating configuration..."
    
    # Check required environment variables
    required_vars=(
        "NODE_ENV"
        "PRODUCTS_API_BASE_URI"
        "RECOMMENDATION_BASE_URI"
        "VOTING_BASE_URI"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "ERROR: Required environment variable $var is not set"
            exit 1
        fi
    done
    
    echo "Configuration validation passed"
}

# Wait for backend services
wait_for_services() {
    echo "Waiting for backend services to be available..."
    
    # Extract and test each service
    services=(
        "$PRODUCTS_API_BASE_URI"
        "$RECOMMENDATION_BASE_URI"
        "$VOTING_BASE_URI"
    )
    
    for service_url in "${services[@]}"; do
        service_name=$(echo "$service_url" | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
        service_port=$(echo "$service_url" | sed -n 's/.*:\([0-9]*\).*/\1/p')
        
        if [ ! -z "$service_name" ] && [ ! -z "$service_port" ]; then
            echo "Waiting for $service_name:$service_port..."
            
            timeout 60 bash -c "
                until curl -f $service_url/health > /dev/null 2>&1 || curl -f $service_url/actuator/health > /dev/null 2>&1 || curl -f $service_url/api/health > /dev/null 2>&1; do
                    echo 'Waiting for $service_name...'
                    sleep 2
                done
            " || echo "WARNING: $service_name did not become available within timeout"
            
            echo "$service_name is available"
        fi
    done
}

# Graceful shutdown handler
shutdown_handler() {
    echo "Received shutdown signal, gracefully shutting down..."
    
    # Kill the main process if it's running
    if [ ! -z "$MAIN_PID" ]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        wait "$MAIN_PID" 2>/dev/null || true
    fi
    
    echo "Frontend service stopped"
    exit 0
}

# Set up signal handlers
trap shutdown_handler SIGTERM SIGINT

# Run startup sequence
validate_config
wait_for_services

echo "Starting Node.js application..."

# Start the main application
if [ "$NODE_ENV" = "development" ]; then
    npm run dev &
else
    npm start &
fi

MAIN_PID=$!

# Wait for the main process
wait "$MAIN_PID"