# Docker Setup and Configuration Guide

This document describes the enhanced Docker setup for the Craftista application with robust database connections and comprehensive testing infrastructure.

## Overview

The Craftista application now includes:

- **Database Services**: MongoDB, PostgreSQL, and Redis with health checks
- **Application Services**: Frontend, Catalogue, Voting, and Recommendation services
- **Enhanced Configuration**: Environment-based configuration management
- **Graceful Startup**: Service dependency management and health checks
- **Monitoring**: Health endpoints and logging

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Frontend     │    │   Catalogue     │    │     Voting      │
│   (Node.js)     │───▶│   (Python)      │◀───│  (Java/Spring)  │
│   Port: 3000    │    │   Port: 5000    │    │   Port: 8080    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └─────────────▶│ Recommendation  │◀─────────────┘
                        │      (Go)       │
                        │   Port: 8081    │
                        └─────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    MongoDB      │    │   PostgreSQL    │    │     Redis       │
│   Port: 27017   │    │   Port: 5432    │    │   Port: 6379    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### 1. Environment Setup

Copy the appropriate environment file:

```bash
# For development
cp .env.development .env

# For production
cp .env.production .env
# Edit .env and set production passwords
```

### 2. Start Services

Use the orchestration script for managed startup:

```bash
# Start all services with dependency management
./scripts/start-services.sh

# Or use Docker Compose directly
docker-compose up -d
```

### 3. Verify Services

Check service status:

```bash
# Using the orchestration script
./scripts/start-services.sh docker-compose.yml .env 300 status

# Or check manually
curl http://localhost:3000/health    # Frontend
curl http://localhost:5000/health    # Catalogue
curl http://localhost:8080/actuator/health  # Voting
curl http://localhost:8081/api/health       # Recommendation
```

## Configuration

### Environment Files

The application supports multiple environment configurations:

- **`.env.example`**: Template with all available options
- **`.env.development`**: Development environment settings
- **`.env.production`**: Production environment settings
- **`.env`**: Active environment (copy from one of the above)

### Key Configuration Options

#### Database Configuration

```bash
# MongoDB
MONGODB_ROOT_USERNAME=admin
MONGODB_ROOT_PASSWORD=your_password
MONGODB_DATABASE=catalogue
MONGODB_MAX_POOL_SIZE=10
MONGODB_CONNECTION_TIMEOUT_MS=20000

# PostgreSQL
POSTGRES_DB=voting
POSTGRES_USER=voting_user
POSTGRES_PASSWORD=your_password
DATABASE_MAX_CONNECTIONS=10
DATABASE_CONNECTION_TIMEOUT=20000

# Redis
REDIS_DATABASE=0
REDIS_MAX_MEMORY=256mb
REDIS_POOL_SIZE=10
CACHE_DEFAULT_TTL=1h
```

#### Application Configuration

```bash
# Environment modes
NODE_ENV=production
FLASK_ENV=production
SPRING_PROFILES_ACTIVE=production
GIN_MODE=release

# Logging levels
CATALOGUE_LOG_LEVEL=INFO
VOTING_LOG_LEVEL=INFO
RECOMMENDATION_LOG_LEVEL=info
```

## Service Details

### Database Services

#### MongoDB (Catalogue Database)

- **Image**: `mongo:7-jammy`
- **Port**: 27017
- **Health Check**: `mongosh --eval "db.adminCommand('ping')"`
- **Data Persistence**: `mongodb_data` volume

#### PostgreSQL (Voting Database)

- **Image**: `postgres:15-alpine`
- **Port**: 5432
- **Health Check**: `pg_isready`
- **Data Persistence**: `postgres_data` volume
- **Migrations**: Flyway-based schema management

#### Redis (Caching Layer)

- **Image**: `redis:7-alpine`
- **Port**: 6379
- **Health Check**: `redis-cli ping`
- **Data Persistence**: `redis_data` volume with AOF

### Application Services

#### Frontend Service

- **Technology**: Node.js/Express
- **Port**: 3000
- **Dependencies**: All backend services
- **Health Check**: `/health` endpoint

#### Catalogue Service

- **Technology**: Python/Flask
- **Port**: 5000
- **Database**: MongoDB
- **Health Check**: `/health` endpoint
- **Features**: Product management, search functionality

#### Voting Service

- **Technology**: Java/Spring Boot
- **Port**: 8080
- **Database**: PostgreSQL
- **Health Check**: `/actuator/health` endpoint
- **Features**: Voting system, data synchronization

#### Recommendation Service

- **Technology**: Go/Gin
- **Port**: 8081
- **Database**: Redis
- **Health Check**: `/api/health` endpoint
- **Features**: Recommendation engine, caching

## Startup Process

### Service Dependencies

The startup process follows this order:

1. **Database Services** (MongoDB, PostgreSQL, Redis)
2. **Catalogue Service** (depends on MongoDB)
3. **Voting & Recommendation Services** (depend on PostgreSQL/Redis and Catalogue)
4. **Frontend Service** (depends on all backend services)

### Health Checks

Each service includes comprehensive health checks:

- **Database connectivity**
- **Connection pool status**
- **Service-specific functionality**

### Graceful Shutdown

All services support graceful shutdown:

- **Signal handling** (SIGTERM, SIGINT)
- **Connection draining**
- **Resource cleanup**

## Monitoring and Logging

### Health Endpoints

| Service        | Health Endpoint        | Details                                   |
| -------------- | ---------------------- | ----------------------------------------- |
| Frontend       | `GET /health`          | Service status                            |
| Catalogue      | `GET /health`          | Database connectivity, pool status        |
| Voting         | `GET /actuator/health` | Spring Boot actuator with database health |
| Recommendation | `GET /api/health`      | Redis connectivity, cache status          |

### Logging Configuration

Structured logging with correlation IDs:

```bash
# Log levels by environment
Development: DEBUG/debug
Production: WARN/warn
```

### Metrics

Available metrics include:

- Connection pool utilization
- Query execution times
- Error rates
- Cache hit/miss ratios

## Troubleshooting

### Common Issues

#### Database Connection Failures

```bash
# Check database service status
docker-compose ps

# Check database logs
docker-compose logs mongodb
docker-compose logs postgres
docker-compose logs redis

# Test database connectivity
docker-compose exec catalogue mongosh --eval "db.adminCommand('ping')"
docker-compose exec voting pg_isready -U voting_user -d voting
docker-compose exec recco redis-cli ping
```

#### Service Startup Issues

```bash
# Check service logs
docker-compose logs catalogue
docker-compose logs voting
docker-compose logs recco
docker-compose logs frontend

# Restart specific service
docker-compose restart catalogue
```

#### Configuration Issues

```bash
# Validate environment variables
docker-compose config

# Check service environment
docker-compose exec catalogue env | grep MONGODB
docker-compose exec voting env | grep DATABASE
```

### Performance Tuning

#### Database Optimization

```bash
# MongoDB
MONGODB_MAX_POOL_SIZE=20        # Increase for high load
MONGODB_CONNECTION_TIMEOUT_MS=30000  # Increase for slow networks

# PostgreSQL
DATABASE_MAX_CONNECTIONS=20     # Increase for high concurrency
DATABASE_CONNECTION_TIMEOUT=30000    # Increase for slow networks

# Redis
REDIS_POOL_SIZE=20             # Increase for high throughput
REDIS_MAX_MEMORY=512mb         # Increase for larger datasets
```

#### Application Tuning

```bash
# Logging (reduce for production)
CATALOGUE_LOG_LEVEL=WARN
VOTING_LOG_LEVEL=WARN
RECOMMENDATION_LOG_LEVEL=warn

# Caching
CACHE_DEFAULT_TTL=2h           # Increase for better performance
```

## Development Workflow

### Local Development

```bash
# Use development environment
cp .env.development .env

# Start with hot reload (if supported)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f
```

### Testing

```bash
# Run integration tests
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

# Run specific service tests
docker-compose exec catalogue python -m pytest
docker-compose exec voting ./mvnw test
```

### Production Deployment

```bash
# Use production environment
cp .env.production .env

# Set production passwords
export MONGODB_PROD_PASSWORD="secure_password"
export POSTGRES_PROD_PASSWORD="secure_password"

# Deploy
./scripts/start-services.sh docker-compose.yml .env.production
```

## Security Considerations

### Database Security

- Use strong passwords in production
- Enable authentication on all databases
- Use encrypted connections where possible
- Regular security updates

### Application Security

- Run services as non-root users
- Use secrets management for sensitive data
- Enable CORS protection
- Implement rate limiting

### Network Security

- Use internal networks for service communication
- Expose only necessary ports
- Implement proper firewall rules
- Use TLS for external connections

## Backup and Recovery

### Database Backups

```bash
# MongoDB backup
docker-compose exec mongodb mongodump --out /backup

# PostgreSQL backup
docker-compose exec postgres pg_dump -U voting_user voting > backup.sql

# Redis backup
docker-compose exec redis redis-cli BGSAVE
```

### Volume Management

```bash
# List volumes
docker volume ls

# Backup volumes
docker run --rm -v mongodb_data:/data -v $(pwd):/backup alpine tar czf /backup/mongodb_backup.tar.gz /data

# Restore volumes
docker run --rm -v mongodb_data:/data -v $(pwd):/backup alpine tar xzf /backup/mongodb_backup.tar.gz -C /
```
