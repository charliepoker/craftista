#!/bin/bash
# Wait for MongoDB to be ready

set -e

host="$1"
port="$2"
timeout="${3:-60}"

echo "Waiting for MongoDB at $host:$port..."

# Wait for MongoDB port to be available
./scripts/wait-for-it.sh "$host:$port" -t "$timeout"

# Additional MongoDB-specific health check
echo "Checking MongoDB health..."
for i in $(seq 1 10); do
    if mongosh --host "$host" --port "$port" --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
        echo "MongoDB is ready!"
        exit 0
    fi
    echo "MongoDB not ready yet, waiting... (attempt $i/10)"
    sleep 2
done

echo "MongoDB failed to become ready within timeout"
exit 1