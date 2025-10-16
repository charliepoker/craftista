#!/bin/bash

# PostgreSQL Migration Script for Voting Service
# This script provides easy access to all PostgreSQL migration operations using Flyway

set -e

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOTING_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
DEFAULT_DB_URL="jdbc:postgresql://localhost:5432/voting"
DEFAULT_DB_USER="voting_user"
DEFAULT_DB_PASSWORD="voting_pass"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
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

# Function to show usage
show_usage() {
    cat << EOF
PostgreSQL Migration Script for Voting Service

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    migrate     Run pending migrations
    info        Show migration status and information
    validate    Validate applied migrations against available ones
    baseline    Baseline an existing database
    clean       Drop all objects in configured schemas (USE WITH CAUTION)
    repair      Repair the schema history table
    rollback    Rollback to a specific version (if supported)
    seed        Run development seed data
    reset       Reset database to clean state and re-run all migrations
    help        Show this help message

Options:
    --url URL               Database JDBC URL (default: $DEFAULT_DB_URL)
    --user USERNAME         Database username (default: $DEFAULT_DB_USER)
    --password PASSWORD     Database password (default: $DEFAULT_DB_PASSWORD)
    --target VERSION        Target migration version (for migrate command)
    --dry-run              Show what would be executed without running
    --verbose              Enable verbose logging

Environment Variables:
    DATABASE_URL           Database JDBC URL
    DATABASE_USER          Database username  
    DATABASE_PASSWORD      Database password
    FLYWAY_URL            Alternative to DATABASE_URL
    FLYWAY_USER           Alternative to DATABASE_USER
    FLYWAY_PASSWORD       Alternative to DATABASE_PASSWORD

Examples:
    $0 migrate                                    # Run all pending migrations
    $0 migrate --target 3                        # Migrate to version 3
    $0 info                                      # Show migration status
    $0 validate                                  # Validate migrations
    $0 seed                                      # Run development seed data
    $0 clean --url jdbc:postgresql://localhost:5432/test  # Clean test database
    $0 reset                                     # Reset and re-run all migrations

EOF
}

# Function to check if Maven is available
check_maven() {
    if ! command -v mvn &> /dev/null; then
        print_error "Maven (mvn) is not installed or not in PATH"
        print_info "Please install Maven to use this script"
        exit 1
    fi
    print_success "Maven found: $(mvn --version | head -n 1)"
}

# Function to check database connection
check_database_connection() {
    local db_url="$1"
    local db_user="$2"
    local db_password="$3"
    
    print_info "Checking database connection..."
    
    cd "$VOTING_DIR"
    
    if mvn flyway:info \
        -Dflyway.url="$db_url" \
        -Dflyway.user="$db_user" \
        -Dflyway.password="$db_password" \
        -q > /dev/null 2>&1; then
        print_success "Database connection successful"
    else
        print_error "Failed to connect to database: $db_url"
        print_info "Please ensure PostgreSQL is running and credentials are correct"
        exit 1
    fi
}

# Function to run Flyway command
run_flyway_command() {
    local command="$1"
    local db_url="$2"
    local db_user="$3"
    local db_password="$4"
    shift 4
    local extra_args=("$@")
    
    print_info "Running Flyway command: $command"
    
    cd "$VOTING_DIR"
    
    local flyway_cmd="mvn flyway:$command"
    flyway_cmd="$flyway_cmd -Dflyway.url=$db_url"
    flyway_cmd="$flyway_cmd -Dflyway.user=$db_user"
    flyway_cmd="$flyway_cmd -Dflyway.password=$db_password"
    
    # Add extra arguments
    for arg in "${extra_args[@]}"; do
        flyway_cmd="$flyway_cmd $arg"
    done
    
    print_info "Executing: $flyway_cmd"
    
    if eval "$flyway_cmd"; then
        print_success "Flyway command '$command' completed successfully!"
    else
        print_error "Flyway command '$command' failed!"
        exit 1
    fi
}

# Function to show migration info
show_migration_info() {
    local db_url="$1"
    local db_user="$2"
    local db_password="$3"
    
    print_info "Migration Status:"
    run_flyway_command "info" "$db_url" "$db_user" "$db_password"
}

# Function to run seed data
run_seed_data() {
    local db_url="$1"
    local db_user="$2"
    local db_password="$3"
    
    print_info "Running development seed data..."
    
    # First ensure we're up to date with migrations
    run_flyway_command "migrate" "$db_url" "$db_user" "$db_password"
    
    print_success "Seed data migration completed!"
}

# Function to reset database
reset_database() {
    local db_url="$1"
    local db_user="$2"
    local db_password="$3"
    
    print_warning "This will completely reset the database!"
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Reset cancelled"
        exit 0
    fi
    
    print_info "Cleaning database..."
    run_flyway_command "clean" "$db_url" "$db_user" "$db_password"
    
    print_info "Running all migrations..."
    run_flyway_command "migrate" "$db_url" "$db_user" "$db_password"
    
    print_success "Database reset completed!"
}

# Parse command line arguments
COMMAND=""
DB_URL="${DATABASE_URL:-${FLYWAY_URL:-$DEFAULT_DB_URL}}"
DB_USER="${DATABASE_USER:-${FLYWAY_USER:-$DEFAULT_DB_USER}}"
DB_PASSWORD="${DATABASE_PASSWORD:-${FLYWAY_PASSWORD:-$DEFAULT_DB_PASSWORD}}"
TARGET_VERSION=""
DRY_RUN=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        migrate|info|validate|baseline|clean|repair|rollback|seed|reset|help)
            COMMAND="$1"
            shift
            ;;
        --url)
            DB_URL="$2"
            shift 2
            ;;
        --user)
            DB_USER="$2"
            shift 2
            ;;
        --password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        --target)
            TARGET_VERSION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
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

# Show help if no command provided
if [[ -z "$COMMAND" ]]; then
    show_usage
    exit 1
fi

# Show help
if [[ "$COMMAND" == "help" ]]; then
    show_usage
    exit 0
fi

# Print configuration
print_info "Migration Configuration:"
print_info "  Command: $COMMAND"
print_info "  Database URL: $DB_URL"
print_info "  Database User: $DB_USER"
print_info "  Target Version: ${TARGET_VERSION:-latest}"
print_info "  Dry Run: $DRY_RUN"
print_info "  Verbose: $VERBOSE"

# Check dependencies
check_maven

# Check database connection (except for help command)
if [[ "$COMMAND" != "help" ]]; then
    check_database_connection "$DB_URL" "$DB_USER" "$DB_PASSWORD"
fi

# Build extra arguments
EXTRA_ARGS=()

if [[ -n "$TARGET_VERSION" ]]; then
    EXTRA_ARGS+=("-Dflyway.target=$TARGET_VERSION")
fi

if [[ "$VERBOSE" == true ]]; then
    EXTRA_ARGS+=("-X")
fi

# Execute command
case $COMMAND in
    migrate)
        run_flyway_command "migrate" "$DB_URL" "$DB_USER" "$DB_PASSWORD" "${EXTRA_ARGS[@]}"
        ;;
    info)
        show_migration_info "$DB_URL" "$DB_USER" "$DB_PASSWORD"
        ;;
    validate)
        run_flyway_command "validate" "$DB_URL" "$DB_USER" "$DB_PASSWORD" "${EXTRA_ARGS[@]}"
        ;;
    baseline)
        run_flyway_command "baseline" "$DB_URL" "$DB_USER" "$DB_PASSWORD" "${EXTRA_ARGS[@]}"
        ;;
    clean)
        print_warning "This will drop all objects in the database!"
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            run_flyway_command "clean" "$DB_URL" "$DB_USER" "$DB_PASSWORD" "${EXTRA_ARGS[@]}"
        else
            print_info "Clean cancelled"
        fi
        ;;
    repair)
        run_flyway_command "repair" "$DB_URL" "$DB_USER" "$DB_PASSWORD" "${EXTRA_ARGS[@]}"
        ;;
    seed)
        run_seed_data "$DB_URL" "$DB_USER" "$DB_PASSWORD"
        ;;
    reset)
        reset_database "$DB_URL" "$DB_USER" "$DB_PASSWORD"
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac

print_success "All operations completed successfully!"