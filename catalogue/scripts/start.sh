#!/bin/bash
# Catalogue Service Startup Script

set -e

echo "Starting Catalogue Service..."

# Configuration validation
validate_config() {
    echo "Validating configuration..."
    
    # Check required environment variables
    required_vars=(
        "DATA_SOURCE"
        "MONGODB_URL"
        "MONGODB_DATABASE"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "ERROR: Required environment variable $var is not set"
            exit 1
        fi
    done
    
    echo "Configuration validation passed"
}

# Wait for database availability
wait_for_database() {
    if [ "$DATA_SOURCE" = "mongodb" ]; then
        echo "Waiting for MongoDB to be available..."
        
        # Extract host and port from MongoDB URL
        # Format: mongodb://user:pass@host:port/database
        MONGO_HOST=$(echo "$MONGODB_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
        MONGO_PORT=$(echo "$MONGODB_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        
        if [ -z "$MONGO_HOST" ] || [ -z "$MONGO_PORT" ]; then
            echo "Could not parse MongoDB host/port from URL: $MONGODB_URL"
            exit 1
        fi
        
        # Wait for MongoDB with timeout
        timeout 60 bash -c "
            until python3 -c \"
import socket
s = socket.create_connection(('$MONGO_HOST', $MONGO_PORT), timeout=3)
s.close()
\" > /dev/null 2>&1; do
                echo 'Waiting for MongoDB...'
                sleep 2
            done
        "
        
        if [ $? -ne 0 ]; then
            echo "ERROR: MongoDB did not become available within timeout"
            exit 1
        fi
        
        echo "MongoDB is available"
    fi
}

# Graceful shutdown handler
shutdown_handler() {
    echo "Received shutdown signal, gracefully shutting down..."
    
    # Kill the main process if it's running
    if [ ! -z "$MAIN_PID" ]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        wait "$MAIN_PID" 2>/dev/null || true
    fi
    
    echo "Catalogue service stopped"
    exit 0
}

# Set up signal handlers
trap shutdown_handler SIGTERM SIGINT

# Run startup sequence
validate_config
wait_for_database

echo "Starting Flask application..."

# Start the main application
if [ "$FLASK_ENV" = "development" ]; then
    python app.py &
else
    gunicorn app:app --bind 0.0.0.0:5000 --workers 4 --timeout 30 &
fi

MAIN_PID=$!

# Wait for the main process
wait "$MAIN_PID"