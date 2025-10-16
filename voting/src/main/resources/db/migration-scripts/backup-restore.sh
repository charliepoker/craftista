#!/bin/bash

# PostgreSQL Backup and Restore Script for Voting Service
# This script provides database backup and restore functionality

set -e

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_DB_HOST="localhost"
DEFAULT_DB_PORT="5432"
DEFAULT_DB_NAME="voting"
DEFAULT_DB_USER="voting_user"
DEFAULT_BACKUP_DIR="./backups"

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
PostgreSQL Backup and Restore Script for Voting Service

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    backup      Create a database backup
    restore     Restore from a backup file
    list        List available backup files
    cleanup     Clean up old backup files
    help        Show this help message

Options:
    --host HOST             Database host (default: $DEFAULT_DB_HOST)
    --port PORT             Database port (default: $DEFAULT_DB_PORT)
    --database DATABASE     Database name (default: $DEFAULT_DB_NAME)
    --user USERNAME         Database username (default: $DEFAULT_DB_USER)
    --password PASSWORD     Database password (will prompt if not provided)
    --backup-dir DIR        Backup directory (default: $DEFAULT_BACKUP_DIR)
    --file FILENAME         Specific backup file for restore
    --format FORMAT         Backup format: plain, custom, tar (default: custom)
    --compress              Enable compression for backups
    --data-only            Backup/restore data only (no schema)
    --schema-only          Backup/restore schema only (no data)
    --keep-days DAYS       Keep backups for specified days (default: 30)
    --verbose              Enable verbose logging

Environment Variables:
    PGHOST                 Database host
    PGPORT                 Database port
    PGDATABASE            Database name
    PGUSER                Database username
    PGPASSWORD            Database password

Examples:
    $0 backup                                    # Create a full backup
    $0 backup --compress --format custom        # Create compressed custom format backup
    $0 backup --data-only                       # Backup data only
    $0 restore --file backup_20240115_143022.sql # Restore from specific file
    $0 list                                     # List available backups
    $0 cleanup --keep-days 7                   # Keep only last 7 days of backups

EOF
}

# Function to check if PostgreSQL tools are available
check_pg_tools() {
    local missing_tools=()
    
    if ! command -v pg_dump &> /dev/null; then
        missing_tools+=("pg_dump")
    fi
    
    if ! command -v pg_restore &> /dev/null; then
        missing_tools+=("pg_restore")
    fi
    
    if ! command -v psql &> /dev/null; then
        missing_tools+=("psql")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing PostgreSQL tools: ${missing_tools[*]}"
        print_info "Please install PostgreSQL client tools"
        exit 1
    fi
    
    print_success "PostgreSQL tools found"
}

# Function to check database connection
check_database_connection() {
    local host="$1"
    local port="$2"
    local database="$3"
    local user="$4"
    
    print_info "Checking database connection..."
    
    if PGPASSWORD="$DB_PASSWORD" psql -h "$host" -p "$port" -U "$user" -d "$database" -c "SELECT 1;" > /dev/null 2>&1; then
        print_success "Database connection successful"
    else
        print_error "Failed to connect to database: $host:$port/$database"
        print_info "Please ensure PostgreSQL is running and credentials are correct"
        exit 1
    fi
}

# Function to create backup directory
create_backup_dir() {
    local backup_dir="$1"
    
    if [ ! -d "$backup_dir" ]; then
        mkdir -p "$backup_dir"
        print_info "Created backup directory: $backup_dir"
    fi
}

# Function to generate backup filename
generate_backup_filename() {
    local format="$1"
    local data_only="$2"
    local schema_only="$3"
    local compress="$4"
    
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local suffix=""
    
    if [ "$data_only" = true ]; then
        suffix="_data_only"
    elif [ "$schema_only" = true ]; then
        suffix="_schema_only"
    fi
    
    case "$format" in
        "plain")
            echo "backup_${timestamp}${suffix}.sql"
            ;;
        "custom")
            if [ "$compress" = true ]; then
                echo "backup_${timestamp}${suffix}.dump.gz"
            else
                echo "backup_${timestamp}${suffix}.dump"
            fi
            ;;
        "tar")
            if [ "$compress" = true ]; then
                echo "backup_${timestamp}${suffix}.tar.gz"
            else
                echo "backup_${timestamp}${suffix}.tar"
            fi
            ;;
        *)
            echo "backup_${timestamp}${suffix}.sql"
            ;;
    esac
}

# Function to create database backup
create_backup() {
    local host="$1"
    local port="$2"
    local database="$3"
    local user="$4"
    local backup_dir="$5"
    local format="$6"
    local compress="$7"
    local data_only="$8"
    local schema_only="$9"
    local verbose="${10}"
    
    create_backup_dir "$backup_dir"
    
    local filename=$(generate_backup_filename "$format" "$data_only" "$schema_only" "$compress")
    local backup_path="$backup_dir/$filename"
    
    print_info "Creating backup: $filename"
    print_info "Format: $format"
    print_info "Compress: $compress"
    print_info "Data only: $data_only"
    print_info "Schema only: $schema_only"
    
    # Build pg_dump command
    local pg_dump_cmd="PGPASSWORD=\"$DB_PASSWORD\" pg_dump"
    pg_dump_cmd="$pg_dump_cmd -h $host -p $port -U $user -d $database"
    
    if [ "$verbose" = true ]; then
        pg_dump_cmd="$pg_dump_cmd --verbose"
    fi
    
    if [ "$data_only" = true ]; then
        pg_dump_cmd="$pg_dump_cmd --data-only"
    elif [ "$schema_only" = true ]; then
        pg_dump_cmd="$pg_dump_cmd --schema-only"
    fi
    
    case "$format" in
        "plain")
            pg_dump_cmd="$pg_dump_cmd --format=plain"
            if [ "$compress" = true ]; then
                pg_dump_cmd="$pg_dump_cmd | gzip > $backup_path"
            else
                pg_dump_cmd="$pg_dump_cmd > $backup_path"
            fi
            ;;
        "custom")
            pg_dump_cmd="$pg_dump_cmd --format=custom"
            if [ "$compress" = true ]; then
                pg_dump_cmd="$pg_dump_cmd --compress=9"
            fi
            pg_dump_cmd="$pg_dump_cmd --file=$backup_path"
            ;;
        "tar")
            pg_dump_cmd="$pg_dump_cmd --format=tar"
            if [ "$compress" = true ]; then
                pg_dump_cmd="$pg_dump_cmd | gzip > $backup_path"
            else
                pg_dump_cmd="$pg_dump_cmd --file=$backup_path"
            fi
            ;;
    esac
    
    print_info "Executing: $pg_dump_cmd"
    
    if eval "$pg_dump_cmd"; then
        local file_size=$(du -h "$backup_path" | cut -f1)
        print_success "Backup created successfully: $backup_path ($file_size)"
        
        # Create metadata file
        local metadata_file="$backup_path.meta"
        cat > "$metadata_file" << EOF
{
    "filename": "$filename",
    "created_at": "$(date -Iseconds)",
    "database": "$database",
    "host": "$host",
    "port": "$port",
    "user": "$user",
    "format": "$format",
    "compressed": $compress,
    "data_only": $data_only,
    "schema_only": $schema_only,
    "size": "$file_size"
}
EOF
        print_info "Metadata saved: $metadata_file"
    else
        print_error "Backup failed!"
        exit 1
    fi
}

# Function to restore from backup
restore_backup() {
    local host="$1"
    local port="$2"
    local database="$3"
    local user="$4"
    local backup_file="$5"
    local verbose="$6"
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    print_warning "This will restore the database from: $backup_file"
    print_warning "This may overwrite existing data!"
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Restore cancelled"
        exit 0
    fi
    
    print_info "Restoring from backup: $backup_file"
    
    # Determine file format based on extension
    local restore_cmd=""
    if [[ "$backup_file" == *.sql ]] || [[ "$backup_file" == *.sql.gz ]]; then
        # Plain SQL format
        if [[ "$backup_file" == *.gz ]]; then
            restore_cmd="gunzip -c $backup_file | PGPASSWORD=\"$DB_PASSWORD\" psql -h $host -p $port -U $user -d $database"
        else
            restore_cmd="PGPASSWORD=\"$DB_PASSWORD\" psql -h $host -p $port -U $user -d $database -f $backup_file"
        fi
    elif [[ "$backup_file" == *.dump ]] || [[ "$backup_file" == *.dump.gz ]]; then
        # Custom format
        restore_cmd="PGPASSWORD=\"$DB_PASSWORD\" pg_restore -h $host -p $port -U $user -d $database"
        if [ "$verbose" = true ]; then
            restore_cmd="$restore_cmd --verbose"
        fi
        restore_cmd="$restore_cmd --clean --if-exists $backup_file"
    elif [[ "$backup_file" == *.tar ]] || [[ "$backup_file" == *.tar.gz ]]; then
        # Tar format
        restore_cmd="PGPASSWORD=\"$DB_PASSWORD\" pg_restore -h $host -p $port -U $user -d $database"
        if [ "$verbose" = true ]; then
            restore_cmd="$restore_cmd --verbose"
        fi
        restore_cmd="$restore_cmd --clean --if-exists $backup_file"
    else
        print_error "Unknown backup file format: $backup_file"
        exit 1
    fi
    
    print_info "Executing: $restore_cmd"
    
    if eval "$restore_cmd"; then
        print_success "Database restored successfully from: $backup_file"
    else
        print_error "Restore failed!"
        exit 1
    fi
}

# Function to list backup files
list_backups() {
    local backup_dir="$1"
    
    if [ ! -d "$backup_dir" ]; then
        print_warning "Backup directory does not exist: $backup_dir"
        return
    fi
    
    print_info "Available backups in: $backup_dir"
    echo
    
    local backup_files=($(find "$backup_dir" -name "backup_*.sql" -o -name "backup_*.dump" -o -name "backup_*.tar" -o -name "backup_*.gz" | sort -r))
    
    if [ ${#backup_files[@]} -eq 0 ]; then
        print_warning "No backup files found"
        return
    fi
    
    printf "%-30s %-20s %-10s %s\n" "FILENAME" "CREATED" "SIZE" "METADATA"
    printf "%-30s %-20s %-10s %s\n" "--------" "-------" "----" "--------"
    
    for backup_file in "${backup_files[@]}"; do
        local filename=$(basename "$backup_file")
        local created=$(date -r "$backup_file" "+%Y-%m-%d %H:%M:%S")
        local size=$(du -h "$backup_file" | cut -f1)
        local metadata_file="$backup_file.meta"
        local has_metadata="No"
        
        if [ -f "$metadata_file" ]; then
            has_metadata="Yes"
        fi
        
        printf "%-30s %-20s %-10s %s\n" "$filename" "$created" "$size" "$has_metadata"
    done
}

# Function to cleanup old backups
cleanup_backups() {
    local backup_dir="$1"
    local keep_days="$2"
    
    if [ ! -d "$backup_dir" ]; then
        print_warning "Backup directory does not exist: $backup_dir"
        return
    fi
    
    print_info "Cleaning up backups older than $keep_days days in: $backup_dir"
    
    local deleted_count=0
    
    # Find and delete old backup files
    while IFS= read -r -d '' file; do
        local filename=$(basename "$file")
        print_info "Deleting old backup: $filename"
        rm -f "$file"
        rm -f "$file.meta"  # Also delete metadata file if it exists
        ((deleted_count++))
    done < <(find "$backup_dir" -name "backup_*" -type f -mtime +$keep_days -print0)
    
    if [ $deleted_count -eq 0 ]; then
        print_info "No old backups found to delete"
    else
        print_success "Deleted $deleted_count old backup files"
    fi
}

# Parse command line arguments
COMMAND=""
DB_HOST="${PGHOST:-$DEFAULT_DB_HOST}"
DB_PORT="${PGPORT:-$DEFAULT_DB_PORT}"
DB_NAME="${PGDATABASE:-$DEFAULT_DB_NAME}"
DB_USER="${PGUSER:-$DEFAULT_DB_USER}"
DB_PASSWORD="${PGPASSWORD:-}"
BACKUP_DIR="$DEFAULT_BACKUP_DIR"
BACKUP_FILE=""
FORMAT="custom"
COMPRESS=false
DATA_ONLY=false
SCHEMA_ONLY=false
KEEP_DAYS=30
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        backup|restore|list|cleanup|help)
            COMMAND="$1"
            shift
            ;;
        --host)
            DB_HOST="$2"
            shift 2
            ;;
        --port)
            DB_PORT="$2"
            shift 2
            ;;
        --database)
            DB_NAME="$2"
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
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --file)
            BACKUP_FILE="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --compress)
            COMPRESS=true
            shift
            ;;
        --data-only)
            DATA_ONLY=true
            shift
            ;;
        --schema-only)
            SCHEMA_ONLY=true
            shift
            ;;
        --keep-days)
            KEEP_DAYS="$2"
            shift 2
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

# Prompt for password if not provided
if [[ -z "$DB_PASSWORD" && "$COMMAND" != "list" && "$COMMAND" != "cleanup" ]]; then
    read -s -p "Database password: " DB_PASSWORD
    echo
fi

# Print configuration
print_info "Backup/Restore Configuration:"
print_info "  Command: $COMMAND"
print_info "  Database: $DB_HOST:$DB_PORT/$DB_NAME"
print_info "  User: $DB_USER"
print_info "  Backup Directory: $BACKUP_DIR"
if [[ -n "$BACKUP_FILE" ]]; then
    print_info "  Backup File: $BACKUP_FILE"
fi
print_info "  Format: $FORMAT"
print_info "  Compress: $COMPRESS"
print_info "  Verbose: $VERBOSE"

# Check dependencies
check_pg_tools

# Check database connection (except for list and cleanup commands)
if [[ "$COMMAND" != "list" && "$COMMAND" != "cleanup" ]]; then
    check_database_connection "$DB_HOST" "$DB_PORT" "$DB_NAME" "$DB_USER"
fi

# Execute command
case $COMMAND in
    backup)
        create_backup "$DB_HOST" "$DB_PORT" "$DB_NAME" "$DB_USER" "$BACKUP_DIR" "$FORMAT" "$COMPRESS" "$DATA_ONLY" "$SCHEMA_ONLY" "$VERBOSE"
        ;;
    restore)
        if [[ -z "$BACKUP_FILE" ]]; then
            print_error "Backup file must be specified with --file option"
            exit 1
        fi
        restore_backup "$DB_HOST" "$DB_PORT" "$DB_NAME" "$DB_USER" "$BACKUP_FILE" "$VERBOSE"
        ;;
    list)
        list_backups "$BACKUP_DIR"
        ;;
    cleanup)
        cleanup_backups "$BACKUP_DIR" "$KEEP_DAYS"
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac

print_success "Operation completed successfully!"