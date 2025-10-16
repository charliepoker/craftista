#!/bin/bash
# Wait for Redis to be ready

set -e

host="$1"
port="$2"
timeout="${3:-60}"

echo "Waiting for Redis at $host:$port..."

# Wait for Redis port to be available
./scripts/wait-for-it.sh "$host:$port" -t "$timeout"

# Additional Redis-specific health check
echo "Checking Redis health..."
for i in $(seq 1 10); do
    if redis-cli -h "$host" -p "$port" ping > /dev/null 2>&1; then
        echo "Redis is ready!"
        exit 0
    fi
    echo "Redis not ready yet, waiting... (attempt $i/10)"
    sleep 2
done

echo "Redis failed to become ready within timeout"
exit 1