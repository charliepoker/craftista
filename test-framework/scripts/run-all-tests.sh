#!/bin/bash

# Comprehensive Test Runner Script
# This script orchestrates the execution of all tests across all services

set -e  # Exit on any error

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_CONFIG="$SCRIPT_DIR/../config/test-config.yml"
RESULTS_DIR="$PROJECT_ROOT/test-results"
LOG_FILE="$RESULTS_DIR/test-execution.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
ENVIRONMENT="local"
SERVICES="all"
PARALLEL=true
CLEANUP=true
VERBOSE=false

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] ${message}${NC}" | tee -a "$LOG_FILE"
}

print_info() {
    print_status "$BLUE" "INFO: $1"
}

print_success() {
    print_status "$GREEN" "SUCCESS: $1"
}

print_warning() {
    print_status "$YELLOW" "WARNING: $1"
}

print_error() {
    print_status "$RED" "ERROR: $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Comprehensive test runner for the Craftista microservices application.

OPTIONS:
    -t, --type TYPE         Test type to run: unit, integration, performance, all (default: all)
    -e, --env ENVIRONMENT   Test environment: local, ci, performance (default: local)
    -s, --services SERVICES Comma-separated list of services or 'all' (default: all)
    -p, --parallel          Run tests in parallel (default: true)
    -n, --no-parallel       Run tests sequentially
    -c, --no-cleanup        Skip cleanup after tests
    -v, --verbose           Verbose output
    -h, --help              Show this help message

EXAMPLES:
    $0                                          # Run all tests for all services
    $0 -t unit                                  # Run only unit tests
    $0 -t integration -s catalogue,voting       # Run integration tests for specific services
    $0 -t performance -e performance            # Run performance tests in performance environment
    $0 -t unit -n                               # Run unit tests sequentially

SERVICES:
    catalogue       Python/Flask service with MongoDB
    voting          Java/Spring Boot service with PostgreSQL  
    recommendation  Go/Gin service with Redis
    frontend        Node.js/Express service

TEST TYPES:
    unit            Fast, isolated unit tests with mocks
    integration     Integration tests with real databases
    performance     Performance and load tests
    all             All test types

ENVIRONMENTS:
    local           Local development environment
    ci              Continuous Integration environment
    performance     Performance testing environment
EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--type)
                TEST_TYPE="$2"
                shift 2
                ;;
            -e|--env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -s|--services)
                SERVICES="$2"
                shift 2
                ;;
            -p|--parallel)
                PARALLEL=true
                shift
                ;;
            -n|--no-parallel)
                PARALLEL=false
                shift
                ;;
            -c|--no-cleanup)
                CLEANUP=false
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check if Docker is available and running
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker is not running"
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check if required tools are available for each service
    local missing_tools=()
    
    # Python for catalogue service
    if [[ "$SERVICES" == "all" || "$SERVICES" == *"catalogue"* ]]; then
        if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
            missing_tools+=("python3")
        fi
        if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
            missing_tools+=("pip3")
        fi
    fi
    
    # Java/Maven for voting service
    if [[ "$SERVICES" == "all" || "$SERVICES" == *"voting"* ]]; then
        if ! command -v java &> /dev/null; then
            missing_tools+=("java")
        fi
        if ! command -v mvn &> /dev/null; then
            missing_tools+=("maven")
        fi
    fi
    
    # Go for recommendation service
    if [[ "$SERVICES" == "all" || "$SERVICES" == *"recommendation"* ]]; then
        if ! command -v go &> /dev/null; then
            missing_tools+=("go")
        fi
    fi
    
    # Node.js for frontend service
    if [[ "$SERVICES" == "all" || "$SERVICES" == *"frontend"* ]]; then
        if ! command -v node &> /dev/null; then
            missing_tools+=("node")
        fi
        if ! command -v npm &> /dev/null; then
            missing_tools+=("npm")
        fi
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    print_success "All prerequisites are met"
}

# Function to setup test environment
setup_environment() {
    print_info "Setting up test environment..."
    
    # Create results directory
    mkdir -p "$RESULTS_DIR"
    
    # Initialize log file
    echo "Test execution started at $(date)" > "$LOG_FILE"
    
    # Start required database containers based on services and test types
    if [[ "$TEST_TYPE" == "integration" || "$TEST_TYPE" == "performance" || "$TEST_TYPE" == "all" ]]; then
        start_database_containers
    fi
    
    print_success "Test environment setup complete"
}

# Function to start database containers
start_database_containers() {
    print_info "Starting database containers..."
    
    local services_array
    if [[ "$SERVICES" == "all" ]]; then
        services_array=("catalogue" "voting" "recommendation")
    else
        IFS=',' read -ra services_array <<< "$SERVICES"
    fi
    
    # Start MongoDB for catalogue service
    if [[ " ${services_array[*]} " =~ " catalogue " ]]; then
        print_info "Starting MongoDB container..."
        docker run -d --name test-mongodb \
            -p 27017:27017 \
            -e MONGO_INITDB_ROOT_USERNAME=testuser \
            -e MONGO_INITDB_ROOT_PASSWORD=testpass \
            -e MONGO_INITDB_DATABASE=testdb \
            mongo:7.0 || print_warning "MongoDB container may already be running"
        
        # Wait for MongoDB to be ready
        wait_for_service "MongoDB" "docker exec test-mongodb mongosh --eval 'db.runCommand(\"ping\")'" 30
    fi
    
    # Start PostgreSQL for voting service
    if [[ " ${services_array[*]} " =~ " voting " ]]; then
        print_info "Starting PostgreSQL container..."
        docker run -d --name test-postgres \
            -p 5432:5432 \
            -e POSTGRES_DB=testdb \
            -e POSTGRES_USER=testuser \
            -e POSTGRES_PASSWORD=testpass \
            postgres:15-alpine || print_warning "PostgreSQL container may already be running"
        
        # Wait for PostgreSQL to be ready
        wait_for_service "PostgreSQL" "docker exec test-postgres pg_isready -U testuser -d testdb" 30
    fi
    
    # Start Redis for recommendation service
    if [[ " ${services_array[*]} " =~ " recommendation " ]]; then
        print_info "Starting Redis container..."
        docker run -d --name test-redis \
            -p 6379:6379 \
            redis:7-alpine || print_warning "Redis container may already be running"
        
        # Wait for Redis to be ready
        wait_for_service "Redis" "docker exec test-redis redis-cli ping" 15
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local service_name=$1
    local health_check_command=$2
    local timeout=${3:-30}
    local counter=0
    
    print_info "Waiting for $service_name to be ready..."
    
    while [[ $counter -lt $timeout ]]; do
        if eval "$health_check_command" &> /dev/null; then
            print_success "$service_name is ready"
            return 0
        fi
        
        sleep 1
        ((counter++))
    done
    
    print_error "$service_name failed to start within $timeout seconds"
    return 1
}

# Function to run tests for a specific service
run_service_tests() {
    local service=$1
    local test_type=$2
    local service_dir="$PROJECT_ROOT/$service"
    local service_results_dir="$RESULTS_DIR/$service"
    
    print_info "Running $test_type tests for $service service..."
    
    # Create service results directory
    mkdir -p "$service_results_dir"
    
    # Change to service directory
    cd "$service_dir"
    
    local exit_code=0
    local start_time=$(date +%s)
    
    case "$service" in
        "catalogue")
            run_catalogue_tests "$test_type" "$service_results_dir"
            exit_code=$?
            ;;
        "voting")
            run_voting_tests "$test_type" "$service_results_dir"
            exit_code=$?
            ;;
        "recommendation")
            run_recommendation_tests "$test_type" "$service_results_dir"
            exit_code=$?
            ;;
        "frontend")
            run_frontend_tests "$test_type" "$service_results_dir"
            exit_code=$?
            ;;
        *)
            print_error "Unknown service: $service"
            return 1
            ;;
    esac
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [[ $exit_code -eq 0 ]]; then
        print_success "$service $test_type tests completed successfully in ${duration}s"
    else
        print_error "$service $test_type tests failed after ${duration}s"
    fi
    
    return $exit_code
}

# Function to run catalogue service tests
run_catalogue_tests() {
    local test_type=$1
    local results_dir=$2
    
    # Install dependencies if needed
    if [[ ! -d "venv" ]]; then
        print_info "Creating Python virtual environment for catalogue service..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    else
        source venv/bin/activate
    fi
    
    case "$test_type" in
        "unit")
            python -m pytest tests/ -v --cov=repository --cov=models \
                --cov-report=html:"$results_dir/coverage" \
                --cov-report=xml:"$results_dir/coverage.xml" \
                --junit-xml="$results_dir/junit.xml" \
                -m "unit" || return 1
            ;;
        "integration")
            python -m pytest tests/integration/ -v \
                --junit-xml="$results_dir/integration-junit.xml" \
                -m "integration" || return 1
            ;;
        "performance")
            python -m pytest tests/performance/ -v \
                --junit-xml="$results_dir/performance-junit.xml" \
                -m "performance" --tb=short || return 1
            ;;
        "all")
            python -m pytest tests/ -v --cov=repository --cov=models \
                --cov-report=html:"$results_dir/coverage" \
                --cov-report=xml:"$results_dir/coverage.xml" \
                --junit-xml="$results_dir/all-junit.xml" || return 1
            ;;
    esac
}

# Function to run voting service tests
run_voting_tests() {
    local test_type=$1
    local results_dir=$2
    
    case "$test_type" in
        "unit")
            mvn test -Dtest="*Test" \
                -Dmaven.test.failure.ignore=false \
                -Dsurefire.reportsDirectory="$results_dir" || return 1
            ;;
        "integration")
            mvn test -Dtest="*IntegrationTest" \
                -Dmaven.test.failure.ignore=false \
                -Dsurefire.reportsDirectory="$results_dir" || return 1
            ;;
        "performance")
            mvn test -Dtest="*PerformanceTest" \
                -Dmaven.test.failure.ignore=false \
                -Dsurefire.reportsDirectory="$results_dir" || return 1
            ;;
        "all")
            mvn test \
                -Dmaven.test.failure.ignore=false \
                -Dsurefire.reportsDirectory="$results_dir" || return 1
            ;;
    esac
}

# Function to run recommendation service tests
run_recommendation_tests() {
    local test_type=$1
    local results_dir=$2
    
    case "$test_type" in
        "unit")
            go test ./tests -v -run "TestUnit" \
                -coverprofile="$results_dir/coverage.out" \
                -json > "$results_dir/unit-results.json" || return 1
            ;;
        "integration")
            go test ./tests -v -run "TestIntegration" \
                -json > "$results_dir/integration-results.json" || return 1
            ;;
        "performance")
            go test ./tests -v -run "TestPerformance" -timeout=10m \
                -json > "$results_dir/performance-results.json" || return 1
            ;;
        "all")
            go test ./tests -v \
                -coverprofile="$results_dir/coverage.out" \
                -json > "$results_dir/all-results.json" || return 1
            ;;
    esac
    
    # Generate HTML coverage report if coverage file exists
    if [[ -f "$results_dir/coverage.out" ]]; then
        go tool cover -html="$results_dir/coverage.out" -o "$results_dir/coverage.html"
    fi
}

# Function to run frontend service tests
run_frontend_tests() {
    local test_type=$1
    local results_dir=$2
    
    # Install dependencies if needed
    if [[ ! -d "node_modules" ]]; then
        print_info "Installing Node.js dependencies for frontend service..."
        npm install
    fi
    
    case "$test_type" in
        "unit")
            npm test -- --reporter json > "$results_dir/unit-results.json" || return 1
            ;;
        "integration")
            npm run test:integration -- --reporter json > "$results_dir/integration-results.json" || return 1
            ;;
        "performance")
            npm run test:performance -- --reporter json > "$results_dir/performance-results.json" || return 1
            ;;
        "all")
            npm test -- --reporter json > "$results_dir/all-results.json" || return 1
            npm run test:coverage || return 1
            ;;
    esac
}

# Function to run tests for all services
run_all_tests() {
    local services_array
    local test_types_array
    local failed_tests=()
    local successful_tests=()
    
    # Parse services
    if [[ "$SERVICES" == "all" ]]; then
        services_array=("catalogue" "voting" "recommendation" "frontend")
    else
        IFS=',' read -ra services_array <<< "$SERVICES"
    fi
    
    # Parse test types
    if [[ "$TEST_TYPE" == "all" ]]; then
        test_types_array=("unit" "integration" "performance")
    else
        test_types_array=("$TEST_TYPE")
    fi
    
    print_info "Running tests for services: ${services_array[*]}"
    print_info "Test types: ${test_types_array[*]}"
    print_info "Parallel execution: $PARALLEL"
    
    # Run tests
    for test_type in "${test_types_array[@]}"; do
        print_info "Starting $test_type tests..."
        
        if [[ "$PARALLEL" == "true" && "$test_type" != "performance" ]]; then
            # Run services in parallel (except performance tests)
            local pids=()
            
            for service in "${services_array[@]}"; do
                run_service_tests "$service" "$test_type" &
                pids+=($!)
            done
            
            # Wait for all parallel tests to complete
            for pid in "${pids[@]}"; do
                if wait "$pid"; then
                    successful_tests+=("$service-$test_type")
                else
                    failed_tests+=("$service-$test_type")
                fi
            done
        else
            # Run services sequentially
            for service in "${services_array[@]}"; do
                if run_service_tests "$service" "$test_type"; then
                    successful_tests+=("$service-$test_type")
                else
                    failed_tests+=("$service-$test_type")
                fi
            done
        fi
    done
    
    # Report results
    print_info "Test execution completed"
    print_success "Successful tests: ${#successful_tests[@]}"
    print_error "Failed tests: ${#failed_tests[@]}"
    
    if [[ ${#failed_tests[@]} -gt 0 ]]; then
        print_error "Failed test combinations:"
        for failed_test in "${failed_tests[@]}"; do
            print_error "  - $failed_test"
        done
        return 1
    fi
    
    return 0
}

# Function to cleanup test environment
cleanup_environment() {
    if [[ "$CLEANUP" == "true" ]]; then
        print_info "Cleaning up test environment..."
        
        # Stop and remove database containers
        docker stop test-mongodb test-postgres test-redis 2>/dev/null || true
        docker rm test-mongodb test-postgres test-redis 2>/dev/null || true
        
        print_success "Cleanup completed"
    else
        print_info "Skipping cleanup (containers left running for debugging)"
    fi
}

# Function to generate test report
generate_test_report() {
    print_info "Generating test report..."
    
    local report_file="$RESULTS_DIR/test-report.html"
    
    cat > "$report_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Craftista Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .success { color: green; }
        .error { color: red; }
        .warning { color: orange; }
        .section { margin: 20px 0; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Craftista Microservices Test Report</h1>
        <p>Generated on: $(date)</p>
        <p>Test Type: $TEST_TYPE</p>
        <p>Environment: $ENVIRONMENT</p>
        <p>Services: $SERVICES</p>
    </div>
    
    <div class="section">
        <h2>Test Results Summary</h2>
        <p>Detailed results can be found in the individual service directories under test-results/</p>
    </div>
    
    <div class="section">
        <h2>Coverage Reports</h2>
        <ul>
            <li><a href="catalogue/coverage/index.html">Catalogue Service Coverage</a></li>
            <li><a href="voting/coverage/index.html">Voting Service Coverage</a></li>
            <li><a href="recommendation/coverage.html">Recommendation Service Coverage</a></li>
            <li><a href="frontend/coverage/index.html">Frontend Service Coverage</a></li>
        </ul>
    </div>
</body>
</html>
EOF
    
    print_success "Test report generated: $report_file"
}

# Main execution function
main() {
    local start_time=$(date +%s)
    
    print_info "Starting Craftista comprehensive test execution"
    print_info "Configuration: Type=$TEST_TYPE, Environment=$ENVIRONMENT, Services=$SERVICES"
    
    # Parse arguments
    parse_arguments "$@"
    
    # Check prerequisites
    check_prerequisites
    
    # Setup environment
    setup_environment
    
    # Run tests
    local test_exit_code=0
    if ! run_all_tests; then
        test_exit_code=1
    fi
    
    # Generate report
    generate_test_report
    
    # Cleanup
    cleanup_environment
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    if [[ $test_exit_code -eq 0 ]]; then
        print_success "All tests completed successfully in ${total_duration}s"
        print_info "Results available in: $RESULTS_DIR"
    else
        print_error "Some tests failed. Total execution time: ${total_duration}s"
        print_info "Check logs and results in: $RESULTS_DIR"
    fi
    
    exit $test_exit_code
}

# Run main function with all arguments
main "$@"