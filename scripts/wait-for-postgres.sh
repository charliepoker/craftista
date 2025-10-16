#!/bin/bash
# Wait for PostgreSQL to be ready

set -e

host="$1"
port="$2"
database="$3"
username="$4"
timeout="${5:-60}"

echo "Waiting for PostgreSQL at $host:$port..."

# Wait for PostgreSQL port to be available
./scripts/wait-for-it.sh "$host:$port" -t "$timeout"

# Additional PostgreSQL-specific health check
echo "Checking PostgreSQL health..."
export PGPASSWORD="$POSTGRES_PASSWORD"
for i in $(seq 1 10); do
    if pg_isready -h "$host" -p "$port" -U "$username" -d "$database" > /dev/null 2>&1; then
        echo "PostgreSQL is ready!"
        exit 0
    fi
    echo "PostgreSQL not ready yet, waiting... (attempt $i/10)"
    sleep 2
done

echo "PostgreSQL failed to become ready within timeout"
exit 1