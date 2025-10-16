#!/bin/bash
# Craftista Services Startup Orchestration Script

set -e

# Configuration
COMPOSE_FILE="${1:-docker-compose.yml}"
ENV_FILE="${2:-.env}"
TIMEOUT="${3:-300}"

echo "Starting Craftista services..."
echo "Using compose file: $COMPOSE_FILE"
echo "Using environment file: $ENV_FILE"

# Check if environment file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "WARNING: Environment file $ENV_FILE not found. Using defaults."
    ENV_FILE=""
fi

# Function to check service health
check_service_health() {
    local service_name="$1"
    local health_url="$2"
    local max_attempts=30
    local attempt=1
    
    echo "Checking health of $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f "$health_url" > /dev/null 2>&1; then
            echo "$service_name is healthy"
            return 0
        fi
        
        echo "Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo "ERROR: $service_name failed to become healthy within timeout"
    return 1
}

# Function to start services in order
start_services() {
    echo "Starting database services..."
    
    # Start databases first
    if [ -n "$ENV_FILE" ]; then
        docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d mongodb postgres redis
    else
        docker-compose -f "$COMPOSE_FILE" up -d mongodb postgres redis
    fi
    
    # Wait for databases to be healthy
    echo "Waiting for databases to be ready..."
    sleep 10
    
    # Check database health
    docker-compose -f "$COMPOSE_FILE" exec -T mongodb mongosh --eval "db.adminCommand('ping')" --quiet || {
        echo "ERROR: MongoDB health check failed"
        return 1
    }
    
    docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U voting_user -d voting || {
        echo "ERROR: PostgreSQL health check failed"
        return 1
    }
    
    docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping || {
        echo "ERROR: Redis health check failed"
        return 1
    }
    
    echo "All databases are ready"
    
    # Start application services
    echo "Starting application services..."
    
    # Start catalogue service first
    if [ -n "$ENV_FILE" ]; then
        docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d catalogue
    else
        docker-compose -f "$COMPOSE_FILE" up -d catalogue
    fi
    
    # Wait for catalogue to be healthy
    check_service_health "catalogue" "http://localhost:5000/health"
    
    # Start voting and recommendation services
    if [ -n "$ENV_FILE" ]; then
        docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d voting recco
    else
        docker-compose -f "$COMPOSE_FILE" up -d voting recco
    fi
    
    # Wait for services to be healthy
    check_service_health "voting" "http://localhost:8080/actuator/health"
    check_service_health "recommendation" "http://localhost:8081/api/health"
    
    # Finally start frontend
    if [ -n "$ENV_FILE" ]; then
        docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d frontend
    else
        docker-compose -f "$COMPOSE_FILE" up -d frontend
    fi
    
    # Wait for frontend to be healthy
    check_service_health "frontend" "http://localhost:3000/health"
    
    echo "All services are running and healthy!"
}

# Function to stop services gracefully
stop_services() {
    echo "Stopping services gracefully..."
    
    # Stop in reverse order
    docker-compose -f "$COMPOSE_FILE" stop frontend
    docker-compose -f "$COMPOSE_FILE" stop voting recco
    docker-compose -f "$COMPOSE_FILE" stop catalogue
    docker-compose -f "$COMPOSE_FILE" stop mongodb postgres redis
    
    echo "All services stopped"
}

# Function to show service status
show_status() {
    echo "Service Status:"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    echo "Service Health:"
    
    # Check each service health
    services=(
        "catalogue:http://localhost:5000/health"
        "voting:http://localhost:8080/actuator/health"
        "recommendation:http://localhost:8081/api/health"
        "frontend:http://localhost:3000/health"
    )
    
    for service_info in "${services[@]}"; do
        service_name=$(echo "$service_info" | cut -d: -f1)
        health_url=$(echo "$service_info" | cut -d: -f2-)
        
        if curl -f "$health_url" > /dev/null 2>&1; then
            echo "✓ $service_name: healthy"
        else
            echo "✗ $service_name: unhealthy"
        fi
    done
}

# Graceful shutdown handler
shutdown_handler() {
    echo "Received shutdown signal..."
    stop_services
    exit 0
}

# Set up signal handlers
trap shutdown_handler SIGTERM SIGINT

# Main execution
case "${4:-start}" in
    "start")
        start_services
        ;;
    "stop")
        stop_services
        ;;
    "status")
        show_status
        ;;
    "restart")
        stop_services
        sleep 5
        start_services
        ;;
    *)
        echo "Usage: $0 [compose-file] [env-file] [timeout] [start|stop|status|restart]"
        echo "  compose-file: Docker compose file (default: docker-compose.yml)"
        echo "  env-file: Environment file (default: .env)"
        echo "  timeout: Startup timeout in seconds (default: 300)"
        echo "  action: Action to perform (default: start)"
        exit 1
        ;;
esac