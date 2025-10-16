# Database Repository Unit Testing Guide

This guide covers the comprehensive unit testing framework implemented for the database repository layer across all Craftista microservices.

## Overview

The unit testing framework provides:

- **Fast, isolated tests** using mocked database operations
- **Comprehensive CRUD operation testing** for all repository methods
- **Edge case and error scenario coverage** including validation and connection failures
- **Mock implementations** for reliable test data management
- **Cross-service consistency** in testing patterns and approaches

## Test Structure

### Catalogue Service (Python/MongoDB)

```
catalogue/
├── tests/
│   ├── __init__.py
│   ├── test_mongodb_repository.py      # Main repository tests
│   ├── test_mock_repository.py         # Mock implementation tests
│   └── mocks/
│       ├── __init__.py
│       └── mock_product_repository.py  # Mock repository implementation
├── pytest.ini                         # Pytest configuration
└── requirements-test.txt               # Test dependencies
```

### Voting Service (Java/Spring Boot)

```
voting/src/test/
├── java/com/example/voting/repository/
│   └── OrigamiRepositoryTest.java      # JPA repository tests
└── resources/
    └── application-test.properties     # Test configuration
```

### Recommendation Service (Go/Redis)

```
recommendation/
├── tests/
│   └── enhanced_redis_repository_test.go  # Redis repository tests
└── go.mod                                 # Go module with test dependencies
```

## Test Categories

### 1. CRUD Operations Testing

- **Create**: Product/Origami/Recommendation creation with validation
- **Read**: Single item retrieval, bulk retrieval with filters and pagination
- **Update**: Partial updates, validation, optimistic locking
- **Delete**: Soft delete, hard delete, cascade operations

### 2. Query and Search Testing

- **Filtering**: Category, price range, tags, active status
- **Text Search**: Full-text search with relevance scoring
- **Pagination**: Skip/limit functionality, large dataset handling
- **Sorting**: Multiple sort criteria, performance optimization

### 3. Error Handling Testing

- **Validation Errors**: Invalid data, constraint violations
- **Connection Errors**: Database unavailability, timeout scenarios
- **Concurrency**: Race conditions, atomic operations
- **Circuit Breaker**: Fallback mechanisms, recovery testing

### 4. Edge Cases Testing

- **Empty Results**: No matches, empty database
- **Large Datasets**: Performance with high volume data
- **Special Characters**: Unicode, SQL injection prevention
- **Null Values**: Proper null handling, optional fields

## Running Tests

### Quick Start

```bash
# Run all unit tests across services
./run_unit_tests.sh
```

### Individual Service Testing

#### Python/Catalogue Service

```bash
cd catalogue
pip install -r requirements-test.txt
python -m pytest tests/ -v --cov=repository --cov=models
```

#### Java/Voting Service

```bash
cd voting
./mvnw test -Dtest=*RepositoryTest
```

#### Go/Recommendation Service

```bash
cd recommendation
go test ./tests/... -v -race -coverprofile=coverage.out
```

## Test Configuration

### Python (pytest.ini)

```ini
[tool:pytest]
testpaths = tests
addopts =
    -v --tb=short --strict-markers
    --cov=repository --cov=models
    --cov-report=term-missing
    --cov-fail-under=80
asyncio_mode = auto
```

### Java (application-test.properties)

```properties
spring.datasource.url=jdbc:h2:mem:testdb
spring.jpa.hibernate.ddl-auto=create-drop
spring.test.database.replace=none
```

### Go (Test Dependencies)

```go
require (
    github.com/stretchr/testify v1.8.4
    github.com/alicebob/miniredis/v2 v2.30.4
)
```

## Mock Implementations

### MockProductRepository (Python)

Provides in-memory implementation of ProductRepository interface:

- Fast test execution without database dependencies
- Configurable failure modes for error testing
- Complete CRUD operation support
- Filter and search functionality matching real implementation

### Key Features:

```python
# Configure failure simulation
repository.set_failure_mode(True, "Database connection failed")

# Add test data directly
repository.add_test_product(sample_product)

# Clear all data between tests
repository.clear_all_products()
```

## Test Data Management

### Sample Data Creation

Each test suite includes fixtures for creating consistent test data:

```python
@pytest.fixture
def sample_products(self, repository):
    products = [
        Product(name="Origami Crane", category="origami", active=True),
        Product(name="Paper Flower", category="craft", active=False)
    ]
    for product in products:
        repository.add_test_product(product)
    return products
```

### Data Isolation

- Each test gets a fresh repository instance
- Test data is automatically cleaned up
- No cross-test contamination

## Coverage Requirements

### Minimum Coverage Targets

- **Repository Layer**: 80% line coverage
- **Model Validation**: 90% line coverage
- **Error Handling**: 100% branch coverage

### Coverage Reports

```bash
# Python coverage report
pytest --cov-report=html:htmlcov

# Java coverage (with JaCoCo)
./mvnw jacoco:report

# Go coverage report
go test -coverprofile=coverage.out
go tool cover -html=coverage.out
```

## Best Practices

### 1. Test Naming Convention

```python
def test_get_product_by_id_success(self):           # Happy path
def test_get_product_by_id_not_found(self):         # Edge case
def test_get_product_by_id_invalid_id(self):        # Error case
def test_create_product_validation_error(self):     # Validation
```

### 2. Assertion Patterns

```python
# Verify successful operation
assert result is not None
assert result.name == expected_name

# Verify error conditions
with pytest.raises(ValidationError) as exc_info:
    await repository.create_product(invalid_data)
assert "specific error message" in str(exc_info.value)

# Verify collections
assert len(products) == expected_count
assert all(product.active for product in products)
```

### 3. Mock Configuration

```python
# Configure mock behavior
mock_collection.find.return_value = mock_cursor
mock_cursor.to_list.return_value = [sample_data]

# Verify mock interactions
mock_collection.find.assert_called_once()
assert call_args[0][0]["active"] is True
```

## Continuous Integration

### GitHub Actions Integration

```yaml
name: Repository Unit Tests
on: [push, pull_request]

jobs:
  test-repositories:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Unit Tests
        run: ./run_unit_tests.sh
```

### Quality Gates

- All tests must pass before merge
- Coverage thresholds must be met
- No new test failures allowed

## Troubleshooting

### Common Issues

#### Python Tests

```bash
# Import errors
export PYTHONPATH="${PYTHONPATH}:$(pwd)/catalogue"

# Async test issues
pip install pytest-asyncio
```

#### Java Tests

```bash
# H2 database issues
./mvnw clean test -Dspring.profiles.active=test

# Maven dependency issues
./mvnw dependency:resolve
```

#### Go Tests

```bash
# Module issues
go mod tidy

# Race condition detection
go test -race ./...
```

### Performance Issues

- Use `@pytest.mark.slow` for long-running tests
- Configure test timeouts appropriately
- Monitor memory usage in large dataset tests

## Future Enhancements

### Planned Improvements

1. **Property-based testing** with hypothesis/QuickCheck
2. **Mutation testing** for test quality validation
3. **Performance benchmarking** integration
4. **Contract testing** between services
5. **Chaos engineering** for resilience testing

### Integration with Development Workflow

1. **Pre-commit hooks** for running fast unit tests
2. **IDE integration** for test-driven development
3. **Test result dashboards** for monitoring
4. **Automated test generation** for new repository methods

## Conclusion

This comprehensive unit testing framework ensures:

- **High confidence** in repository layer functionality
- **Fast feedback** during development
- **Consistent quality** across all microservices
- **Maintainable test code** with clear patterns
- **Comprehensive coverage** of functionality and edge cases

The framework supports both test-driven development and regression testing, providing a solid foundation for the database testing improvements initiative.
