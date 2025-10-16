#!/bin/bash

# MongoDB Migration Script for Catalogue Service
# This script provides easy access to all MongoDB migration operations

set -e

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CATALOGUE_DIR="$(dirname "$SCRIPT_DIR")"
DEFAULT_MONGODB_URL="mongodb://catalogue_user:catalogue_pass@localhost:27017/catalogue"
DEFAULT_DATABASE="catalogue"
DEFAULT_JSON_FILE="products.json"

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
MongoDB Migration Script for Catalogue Service

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    full        Run complete migration (data + indexes + validation)
    data        Run data migration only
    index       Run index creation only
    validate    Run data validation only
    help        Show this help message

Options:
    --mongodb-url URL       MongoDB connection URL (default: $DEFAULT_MONGODB_URL)
    --database NAME         Database name (default: $DEFAULT_DATABASE)
    --json-file PATH        JSON file path for data migration (default: $DEFAULT_JSON_FILE)
    --dry-run              Run in dry-run mode (no actual changes)
    --cleanup              Perform data cleanup during validation
    --verbose              Enable verbose logging

Environment Variables:
    MONGODB_URL            MongoDB connection URL
    MONGODB_DATABASE       MongoDB database name
    JSON_FILE_PATH         Path to JSON file for migration

Examples:
    $0 full                                    # Run complete migration
    $0 full --dry-run                         # Run complete migration in dry-run mode
    $0 data --json-file custom_products.json  # Migrate from custom JSON file
    $0 index                                  # Create indexes only
    $0 validate --cleanup                     # Validate and cleanup data
    $0 full --mongodb-url mongodb://localhost:27017/test  # Use custom MongoDB URL

EOF
}

# Function to check if Python dependencies are available
check_dependencies() {
    print_info "Checking Python dependencies..."
    
    cd "$CATALOGUE_DIR"
    
    if ! python3 -c "import motor, pymongo, pydantic" 2>/dev/null; then
        print_error "Required Python packages not found. Please install dependencies:"
        print_info "pip install -r requirements.txt"
        exit 1
    fi
    
    print_success "Dependencies check passed"
}

# Function to check MongoDB connection
check_mongodb_connection() {
    local mongodb_url="$1"
    
    print_info "Checking MongoDB connection..."
    
    if python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_connection():
    try:
        client = AsyncIOMotorClient('$mongodb_url', serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        client.close()
        return True
    except Exception as e:
        print(f'Connection failed: {e}')
        return False

result = asyncio.run(check_connection())
exit(0 if result else 1)
"; then
        print_success "MongoDB connection successful"
    else
        print_error "Failed to connect to MongoDB at: $mongodb_url"
        print_info "Please ensure MongoDB is running and the connection URL is correct"
        exit 1
    fi
}

# Function to run migration
run_migration() {
    local mode="$1"
    shift
    local args=("$@")
    
    print_info "Running migration mode: $mode"
    
    cd "$CATALOGUE_DIR"
    
    # Build Python command
    local python_cmd="python3 migrations/run_migrations.py --mode $mode"
    
    # Add arguments
    for arg in "${args[@]}"; do
        python_cmd="$python_cmd $arg"
    done
    
    print_info "Executing: $python_cmd"
    
    if eval "$python_cmd"; then
        print_success "Migration completed successfully!"
    else
        print_error "Migration failed!"
        exit 1
    fi
}

# Parse command line arguments
COMMAND=""
MONGODB_URL="${MONGODB_URL:-$DEFAULT_MONGODB_URL}"
DATABASE="${MONGODB_DATABASE:-$DEFAULT_DATABASE}"
JSON_FILE="${JSON_FILE_PATH:-$DEFAULT_JSON_FILE}"
DRY_RUN=false
CLEANUP=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        full|data|index|validate|help)
            COMMAND="$1"
            shift
            ;;
        --mongodb-url)
            MONGODB_URL="$2"
            shift 2
            ;;
        --database)
            DATABASE="$2"
            shift 2
            ;;
        --json-file)
            JSON_FILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --cleanup)
            CLEANUP=true
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
print_info "  MongoDB URL: $MONGODB_URL"
print_info "  Database: $DATABASE"
print_info "  JSON File: $JSON_FILE"
print_info "  Dry Run: $DRY_RUN"
print_info "  Cleanup: $CLEANUP"
print_info "  Verbose: $VERBOSE"

# Check dependencies
check_dependencies

# Check MongoDB connection
check_mongodb_connection "$MONGODB_URL"

# Build migration arguments
MIGRATION_ARGS=()
MIGRATION_ARGS+=("--mongodb-url" "$MONGODB_URL")
MIGRATION_ARGS+=("--database" "$DATABASE")

if [[ "$COMMAND" == "full" || "$COMMAND" == "data" ]]; then
    MIGRATION_ARGS+=("--json-file" "$JSON_FILE")
fi

if [[ "$DRY_RUN" == true ]]; then
    MIGRATION_ARGS+=("--dry-run")
fi

if [[ "$CLEANUP" == true ]]; then
    MIGRATION_ARGS+=("--cleanup")
fi

# Run migration
run_migration "$COMMAND" "${MIGRATION_ARGS[@]}"

print_success "All operations completed successfully!"