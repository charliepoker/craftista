# Comprehensive Testing Framework

This directory contains the comprehensive testing framework for the Craftista microservices application. The framework provides unified testing capabilities across all services with support for unit tests, integration tests, and performance tests.

## 🏗️ Framework Structure

```
test-framework/
├── config/
│   └── test-config.yml          # Central test configuration
├── scripts/
│   ├── run-all-tests.sh         # Main test orchestration script
│   ├── setup-test-environment.py # Environment setup and management
│   └── generate-test-report.py  # Comprehensive report generation
├── fixtures/
│   ├── catalogue/               # Test data for catalogue service
│   ├── voting/                  # Test data for voting service
│   └── recommendation/          # Test data for recommendation service
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.8+ (for catalogue service and framework scripts)
- Java 17+ and Maven (for voting service)
- Go 1.19+ (for recommendation service)
- Node.js 16+ and npm (for frontend service)

### Running All Tests

```bash
# Run all tests for all services
./test-framework/scripts/run-all-tests.sh

# Run only unit tests
./test-framework/scripts/run-all-tests.sh --type unit

# Run tests for specific services
./test-framework/scripts/run-all-tests.sh --services catalogue,voting

# Run performance tests
./test-framework/scripts/run-all-tests.sh --type performance --env performance
```

### Setting Up Test Environment

```bash
# Setup test environment with databases
python3 test-framework/scripts/setup-test-environment.py

# Setup for specific services only
python3 test-framework/scripts/setup-test-environment.py --services catalogue,voting

# Cleanup test environment
python3 test-framework/scripts/setup-test-environment.py --cleanup
```

### Generating Test Reports

```bash
# Generate comprehensive test report
python3 test-framework/scripts/generate-test-report.py

# Specify custom directories
python3 test-framework/scripts/generate-test-report.py --results-dir ./test-results --output-dir ./reports
```

## 📋 Test Types

### Unit Tests

- **Purpose**: Fast, isolated tests with mocked dependencies
- **Scope**: Individual functions, classes, and modules
- **Duration**: < 10 seconds per service
- **Dependencies**: None (uses mocks)

### Integration Tests

- **Purpose**: Test service integration with real databases
- **Scope**: Database operations, API endpoints, service interactions
- **Duration**: 1-5 minutes per service
- **Dependencies**: Docker containers (MongoDB, PostgreSQL, Redis)

### Performance Tests

- **Purpose**: Validate performance under load
- **Scope**: Database operations, concurrent access, throughput
- **Duration**: 5-10 minutes per service
- **Dependencies**: Docker containers with realistic data volumes

## 🔧 Configuration

The framework is configured via `test-framework/config/test-config.yml`. Key sections:

### Services Configuration

```yaml
services:
  catalogue:
    name: "Catalogue Service (Python/Flask)"
    database: "mongodb"
    test_types:
      unit:
        enabled: true
        command: "python -m pytest tests/ -v --cov=repository"
```

### Database Configuration

```yaml
databases:
  mongodb:
    container_image: "mongo:7.0"
    port: 27017
    environment:
      MONGO_INITDB_ROOT_USERNAME: "testuser"
```

### Performance Thresholds

```yaml
performance_thresholds:
  response_time:
    p50: 100 # 50th percentile in milliseconds
    p95: 500 # 95th percentile in milliseconds
  throughput:
    min_requests_per_second: 100
```

## 📊 Test Results and Reports

### Results Structure

```
test-results/
├── catalogue/
│   ├── coverage/           # HTML coverage reports
│   ├── junit.xml          # JUnit test results
│   └── coverage.xml       # Coverage data
├── voting/
├── recommendation/
├── frontend/
└── test-execution.log     # Execution logs
```

### Report Formats

- **HTML Report**: Comprehensive visual report (`test-report.html`)
- **JSON Report**: Machine-readable results (`test-report.json`)
- **Text Summary**: Quick overview (`test-summary.txt`)

## 🎯 Service-Specific Testing

### Catalogue Service (Python/Flask + MongoDB)

**Unit Tests:**

```bash
cd catalogue
python -m pytest tests/ -v -m unit
```

**Integration Tests:**

```bash
cd catalogue
python -m pytest tests/integration/ -v -m integration
```

**Performance Tests:**

```bash
cd catalogue
python -m pytest tests/performance/ -v -m performance
```

**Key Test Areas:**

- MongoDB repository operations
- Product CRUD operations
- Search functionality
- Data validation and sanitization
- Connection pooling and error handling

### Voting Service (Java/Spring Boot + PostgreSQL)

**Unit Tests:**

```bash
cd voting
mvn test -Dtest="*Test"
```

**Integration Tests:**

```bash
cd voting
mvn test -Dtest="*IntegrationTest"
```

**Performance Tests:**

```bash
cd voting
mvn test -Dtest="*PerformanceTest"
```

**Key Test Areas:**

- JPA repository operations
- Vote counting and synchronization
- Transaction management
- Data consistency under concurrent load
- PostgreSQL-specific features

### Recommendation Service (Go/Gin + Redis)

**Unit Tests:**

```bash
cd recommendation
go test ./tests -v -run TestUnit
```

**Integration Tests:**

```bash
cd recommendation
go test ./tests -v -run TestIntegration
```

**Performance Tests:**

```bash
cd recommendation
go test ./tests -v -run TestPerformance
```

**Key Test Areas:**

- Redis caching operations
- Recommendation algorithms
- Cache invalidation strategies
- Connection pool management
- High-throughput scenarios

### Frontend Service (Node.js/Express)

**Unit Tests:**

```bash
cd frontend
npm test
```

**Performance Tests:**

```bash
cd frontend
npm run test:performance
```

**Key Test Areas:**

- API aggregation
- Error handling for downstream services
- Response time under load
- Memory usage patterns
- Concurrent request handling

## 🔍 Performance Testing Details

### Database Performance Tests

**Catalogue Service (MongoDB):**

- High-volume read operations (>1000 ops/sec)
- Concurrent write operations
- Text search performance
- Index utilization
- Memory usage under sustained load

**Voting Service (PostgreSQL):**

- Concurrent vote operations
- Transaction isolation
- Bulk update operations
- Connection pool stress testing
- Query optimization validation

**Recommendation Service (Redis):**

- Cache hit/miss ratios
- High-throughput caching
- Connection pool performance
- Memory usage patterns
- Latency under load

### Performance Thresholds

| Metric              | Threshold     | Service |
| ------------------- | ------------- | ------- |
| Response Time (P95) | < 500ms       | All     |
| Throughput          | > 100 req/sec | All     |
| Error Rate          | < 1%          | All     |
| Memory Usage        | < 512MB       | All     |
| CPU Usage           | < 80%         | All     |

## 🐛 Troubleshooting

### Common Issues

**Docker Container Issues:**

```bash
# Check container status
docker ps -a

# View container logs
docker logs test-mongodb
docker logs test-postgres
docker logs test-redis

# Restart containers
python3 test-framework/scripts/setup-test-environment.py --cleanup
python3 test-framework/scripts/setup-test-environment.py
```

**Test Failures:**

```bash
# Run with verbose output
./test-framework/scripts/run-all-tests.sh --verbose

# Run specific test type only
./test-framework/scripts/run-all-tests.sh --type unit

# Check test logs
cat test-results/test-execution.log
```

**Performance Test Issues:**

```bash
# Run performance tests with extended timeout
./test-framework/scripts/run-all-tests.sh --type performance --env performance

# Check system resources
docker stats
```

### Environment Variables

```bash
# Skip integration tests if Docker unavailable
export SKIP_INTEGRATION_TESTS=true

# Increase test timeouts
export TEST_TIMEOUT_MULTIPLIER=2.0

# Enable debug logging
export TEST_DEBUG=true
```

## 📈 Continuous Integration

### GitHub Actions Integration

The framework integrates with CI/CD pipelines:

```yaml
name: Comprehensive Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run comprehensive tests
        run: ./test-framework/scripts/run-all-tests.sh --env ci
      - name: Generate reports
        run: python3 test-framework/scripts/generate-test-report.py
      - name: Upload test results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: test-results/
```

### Quality Gates

The framework enforces quality gates:

- Minimum 80% code coverage
- Maximum 1% test failure rate
- Performance thresholds compliance
- No critical security vulnerabilities

## 🔧 Extending the Framework

### Adding New Test Types

1. Update `test-config.yml`:

```yaml
services:
  your_service:
    test_types:
      security:
        enabled: true
        command: "your-security-test-command"
```

2. Add test execution logic in `run-all-tests.sh`

3. Update report generation in `generate-test-report.py`

### Adding New Services

1. Create service configuration in `test-config.yml`
2. Add test fixtures in `test-framework/fixtures/your_service/`
3. Implement service-specific test execution logic
4. Update documentation

### Custom Performance Metrics

1. Extend performance test classes
2. Add metrics collection in test methods
3. Update report generation to include new metrics
4. Set appropriate thresholds in configuration

## 📚 Best Practices

### Test Organization

- Keep unit tests fast (< 1 second each)
- Use descriptive test names
- Group related tests in test classes
- Mock external dependencies in unit tests

### Performance Testing

- Use realistic data volumes
- Test under various load conditions
- Monitor resource usage
- Set appropriate timeouts

### Test Data Management

- Use fixtures for consistent test data
- Clean up test data after tests
- Avoid dependencies between tests
- Use factories for dynamic test data

### Error Handling

- Test both success and failure scenarios
- Validate error messages and codes
- Test edge cases and boundary conditions
- Ensure graceful degradation

## 🤝 Contributing

When adding new tests:

1. Follow existing patterns and conventions
2. Update configuration files as needed
3. Add appropriate documentation
4. Ensure tests are deterministic and reliable
5. Include both positive and negative test cases

## 📞 Support

For issues with the testing framework:

1. Check the troubleshooting section
2. Review test execution logs
3. Verify Docker containers are running
4. Check service-specific documentation
5. Create an issue with detailed error information

---

This comprehensive testing framework ensures reliable, maintainable, and performant microservices through systematic testing at all levels.
