# Stage 1: Build stage 
FROM python:3.11-slim AS builder

# Set the working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirement file 
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY . .

# Run the specific test file before proceeding to the final build stage
RUN python -m unittest test_app.py

# Stage 2: Runtime stage
FROM python:3.11-slim

# Install runtime dependencies for database clients and MongoDB shell
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    gnupg \
    && curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg \
    && echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] http://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list \
    && apt-get update && apt-get install -y mongodb-mongosh \
    && rm -rf /var/lib/apt/lists/* /usr/share/keyrings/mongodb-server-7.0.gpg

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set the working directory
WORKDIR /app

# Copy only the necessary files from the build stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Make startup script executable
RUN chmod +x /app/scripts/start.sh

# Set the ownership of the application directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose port 5000 for external access to the application.
EXPOSE 5000

# Use the startup script as entry point
ENTRYPOINT ["/app/scripts/start.sh"]





