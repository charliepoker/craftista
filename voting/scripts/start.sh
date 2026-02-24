#!/bin/bash
# Voting Service Startup Script

set -e

echo "Starting Voting Service..."

# Configuration validation
validate_config() {
    echo "Validating configuration..."
    
    # Check required environment variables
    required_vars=(
        "DATABASE_URL"
        "DATABASE_USERNAME"
        "DATABASE_PASSWORD"
        "SPRING_PROFILES_ACTIVE"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "ERROR: Required environment variable $var is not set"
            exit 1
        fi
    done
    
    # Validate database URL format
    if [[ ! "$DATABASE_URL" =~ ^jdbc:postgresql:// ]]; then
        echo "ERROR: Invalid DATABASE_URL format. Expected jdbc:postgresql://..."
        exit 1
    fi
    
    echo "Configuration validation passed"
}

# Wait for database availability
wait_for_database() {
    echo "Waiting for PostgreSQL to be available..."
    
    # Extract host and port from JDBC URL
    # Format: jdbc:postgresql://host:port/database
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
    
    if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ] || [ -z "$DB_NAME" ]; then
        echo "Could not parse database connection details from URL: $DATABASE_URL"
        exit 1
    fi
    
    # Wait for PostgreSQL with timeout
    export PGPASSWORD="$DATABASE_PASSWORD"
    timeout 60 bash -c "
        until pg_isready -h $DB_HOST -p $DB_PORT -U $DATABASE_USERNAME -d $DB_NAME > /dev/null 2>&1; do
            echo 'Waiting for PostgreSQL...'
            sleep 2
        done
    "
    
    if [ $? -ne 0 ]; then
        echo "ERROR: PostgreSQL did not become available within timeout"
        exit 1
    fi
    
    echo "PostgreSQL is available"
}

# Wait for catalogue service
wait_for_catalogue() {
    # Skip catalogue wait for faster startup - service will retry on its own
    if [ "${SKIP_CATALOGUE_WAIT:-true}" = "true" ]; then
        echo "Skipping Catalogue service wait (will retry on first request)"
        return 0
    fi
    
    if [ ! -z "$CATALOGUE_SERVICE_URL" ]; then
        echo "Waiting for Catalogue service to be available..."
        
        # Extract host and port from catalogue URL
        CATALOGUE_HOST=$(echo "$CATALOGUE_SERVICE_URL" | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
        CATALOGUE_PORT=$(echo "$CATALOGUE_SERVICE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        
        if [ ! -z "$CATALOGUE_HOST" ] && [ ! -z "$CATALOGUE_PORT" ]; then
            # Try for 30 seconds max
            for i in {1..15}; do
                if curl -f http://$CATALOGUE_HOST:$CATALOGUE_PORT/api/products > /dev/null 2>&1; then
                    echo "Catalogue service is available"
                    return 0
                fi
                echo "Waiting for Catalogue service... (attempt $i/15)"
                sleep 2
            done
            echo "WARNING: Catalogue service did not become available, continuing anyway..."
        fi
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
    
    echo "Voting service stopped"
    exit 0
}

# Set up signal handlers
trap shutdown_handler SIGTERM SIGINT

# Run startup sequence
validate_config
wait_for_database
wait_for_catalogue

echo "Starting Spring Boot application..."

# JVM optimizations for faster startup
JAVA_OPTS="${JAVA_OPTS:--XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -XX:+TieredCompilation -XX:TieredStopAtLevel=1 -noverify}"

# Start the main application
java $JAVA_OPTS -jar voting.jar &
MAIN_PID=$!

# Wait for the main process
wait "$MAIN_PID"