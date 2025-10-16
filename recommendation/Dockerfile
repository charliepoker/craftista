# Stage 1: Build stage
FROM golang:1.22.0-alpine AS builder

# Set the working directory inside the container
WORKDIR /app

# Copy Go module files and download dependencies first
COPY go.mod go.sum ./
RUN go mod download

# Copy the rest of the application code
COPY . .

# Build the Go application
RUN go build -o recommendation_app

# Stage 2: Runtime stage
FROM golang:1.22.0-alpine

# Install runtime dependencies
RUN apk add --no-cache \
    curl \
    redis \
    bash

# Set the working directory for the runtime stage
WORKDIR /app

# Copy the built binary from the builder stage
COPY --from=builder /app/recommendation_app .

# Copy the templates and config.json to the runtime stage
COPY --from=builder /app/templates ./templates
COPY --from=builder /app/config.json ./config.json
COPY --from=builder /app/static ./static

# Copy startup scripts
COPY --from=builder /app/scripts ./scripts

# Make startup script executable
RUN chmod +x /app/scripts/start.sh

# Expose the port your app runs on
EXPOSE 8080

# Use the startup script as entry point
ENTRYPOINT ["/app/scripts/start.sh"]

# 