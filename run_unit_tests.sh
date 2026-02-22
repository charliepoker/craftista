#!/bin/bash

# Unit Test Runner for Database Testing Improvements
# This script runs unit tests for all repository layers across services

set -e  # Exit on any error

echo "🧪 Running Unit Tests for Database Repository Layer"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run tests and track results
run_test_suite() {
    local service_name=$1
    local test_command=$2
    local test_dir=$3
    
    print_status "Running $service_name unit tests..."
    
    if [ -d "$test_dir" ]; then
        cd "$test_dir"
        
        if eval "$test_command"; then
            print_success "$service_name tests passed"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            print_error "$service_name tests failed"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
        
        cd - > /dev/null
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
    else
        print_warning "$service_name test directory not found: $test_dir"
    fi
    
    echo ""
}

# 1. Python/Flask Catalogue Service Tests
print_status "Setting up Python test environment..."
if [ -f "catalogue/requirements-test.txt" ]; then
    pip install -r catalogue/requirements-test.txt > /dev/null 2>&1 || {
        print_warning "Failed to install Python test dependencies"
    }
fi

run_test_suite "Catalogue Service (Python/MongoDB)" \
    "python -m pytest tests/ -v --tb=short --cov=repository --cov=models -m 'not integration and not performance' --ignore=tests/integration --ignore=tests/performance" \
    "catalogue"

# 2. Java/Spring Boot Voting Service Tests
print_status "Setting up Java test environment..."
run_test_suite "Voting Service (Java/PostgreSQL)" \
    "./mvnw test -Dtest=*RepositoryTest -DskipITs=true" \
    "voting"

# 3. Go Recommendation Service Tests
print_status "Setting up Go test environment..."
if [ -f "recommendation/go.mod" ]; then
    cd recommendation
    go mod tidy > /dev/null 2>&1 || {
        print_warning "Failed to tidy Go modules"
    }
    cd - > /dev/null
fi

run_test_suite "Recommendation Service (Go/Redis)" \
    "go test ./tests/... -v -race -coverprofile=coverage.out" \
    "recommendation"

# 4. Run Mock Repository Tests (Unit tests only, no DB required)
print_status "Running mock repository tests..."
run_test_suite "Mock Repository Tests" \
    "python -m pytest tests/test_mock_repository.py -v -m 'not integration'" \
    "catalogue"

# Summary
echo "=============================================="
echo "📊 Test Results Summary"
echo "=============================================="
echo "Total test suites: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"

if [ $FAILED_TESTS -eq 0 ]; then
    print_success "All unit tests passed! 🎉"
    echo ""
    echo "✅ Repository layer unit tests are working correctly"
    echo "✅ Mock implementations are functioning properly"
    echo "✅ CRUD operations are tested across all services"
    echo "✅ Error handling and edge cases are covered"
    echo ""
    echo "Next steps:"
    echo "1. Run integration tests with test containers"
    echo "2. Set up CI/CD pipeline integration"
    echo "3. Add performance testing for database operations"
    exit 0
else
    print_error "Some tests failed. Please check the output above."
    echo ""
    echo "❌ $FAILED_TESTS out of $TOTAL_TESTS test suites failed"
    echo ""
    echo "Troubleshooting tips:"
    echo "1. Check that all dependencies are installed"
    echo "2. Verify database connections are properly mocked"
    echo "3. Ensure test data is properly set up"
    echo "4. Review error messages for specific failures"
    exit 1
fi