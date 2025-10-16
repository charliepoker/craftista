# PostgreSQL Database Migrations for Voting Service

This directory contains all database migration scripts and tools for the Voting Service using Flyway for schema versioning and migration management.

## Directory Structure

```
db/
├── migration/                    # Flyway migration scripts
│   ├── V1__Create_origami_table.sql
│   ├── V2__Data_migration_from_catalogue.sql
│   ├── V3__Add_audit_and_performance_enhancements.sql
│   └── V4__Add_development_seed_data.sql
├── migration-scripts/           # Management scripts
│   ├── migrate.sh              # Main migration management script
│   └── backup-restore.sh       # Database backup and restore script
└── README.md                   # This file
```

## Migration Scripts Overview

### V1: Create Origami Table

- Creates the main `origami` table with proper constraints and indexes
- Adds audit fields (`created_at`, `updated_at`, `version`)
- Creates performance indexes for common query patterns
- Includes automatic timestamp update triggers
- Inserts initial seed data

### V2: Data Migration and Sync Functions

- Creates functions for syncing data from Catalogue service
- Adds `sync_history` table for tracking synchronization events
- Implements upsert functionality for origami data
- Creates views for easy access to statistics
- Adds data consistency management functions

### V3: Audit and Performance Enhancements

- Adds comprehensive audit logging with `origami_audit` table
- Creates application metrics tracking system
- Implements materialized views for performance optimization
- Adds database health check functionality
- Creates data cleanup and maintenance functions
- Enables full-text search capabilities

### V4: Development Seed Data

- Adds comprehensive test data for development environments
- Creates sample origami entries with various vote distributions
- Includes edge case testing data (special characters, unicode, long names)
- Adds utility functions for resetting and generating test data
- Provides sample metrics and audit data

## Quick Start

### Prerequisites

1. **Java 17+** and **Maven** installed
2. **PostgreSQL 12+** running and accessible
3. Database and user created with appropriate permissions

### Environment Setup

Set the following environment variables or use the script parameters:

```bash
export DATABASE_URL="jdbc:postgresql://localhost:5432/voting"
export DATABASE_USER="voting_user"
export DATABASE_PASSWORD="voting_pass"

# Alternative Flyway-specific variables
export FLYWAY_URL="jdbc:postgresql://localhost:5432/voting"
export FLYWAY_USER="voting_user"
export FLYWAY_PASSWORD="voting_pass"
```

### Running Migrations

#### Using the Migration Script (Recommended)

```bash
# Navigate to the migration scripts directory
cd src/main/resources/db/migration-scripts

# Make scripts executable (if not already)
chmod +x migrate.sh backup-restore.sh

# Run all pending migrations
./migrate.sh migrate

# Check migration status
./migrate.sh info

# Run with custom database
./migrate.sh migrate --url jdbc:postgresql://localhost:5432/test_db --user test_user --password test_pass
```

#### Using Maven Directly

```bash
# From the voting service root directory
mvn flyway:migrate
mvn flyway:info
mvn flyway:validate
```

## Migration Management

### Available Commands

#### Migration Script (`migrate.sh`)

```bash
./migrate.sh [COMMAND] [OPTIONS]

Commands:
  migrate     # Run pending migrations
  info        # Show migration status
  validate    # Validate applied migrations
  baseline    # Baseline existing database
  clean       # Drop all objects (USE WITH CAUTION)
  repair      # Repair schema history table
  seed        # Run development seed data
  reset       # Reset database and re-run all migrations
  help        # Show help

Options:
  --url URL               # Database JDBC URL
  --user USERNAME         # Database username
  --password PASSWORD     # Database password
  --target VERSION        # Target migration version
  --dry-run              # Show what would be executed
  --verbose              # Enable verbose logging
```

#### Examples

```bash
# Run all migrations
./migrate.sh migrate

# Migrate to specific version
./migrate.sh migrate --target 3

# Check current status
./migrate.sh info

# Validate migrations
./migrate.sh validate

# Run development seed data
./migrate.sh seed

# Reset database (clean + migrate)
./migrate.sh reset
```

### Backup and Restore

#### Backup Script (`backup-restore.sh`)

```bash
./backup-restore.sh [COMMAND] [OPTIONS]

Commands:
  backup      # Create database backup
  restore     # Restore from backup
  list        # List available backups
  cleanup     # Clean up old backups
  help        # Show help

Options:
  --host HOST             # Database host
  --port PORT             # Database port
  --database DATABASE     # Database name
  --user USERNAME         # Database username
  --password PASSWORD     # Database password
  --backup-dir DIR        # Backup directory
  --file FILENAME         # Backup file for restore
  --format FORMAT         # Backup format (plain, custom, tar)
  --compress              # Enable compression
  --data-only            # Backup data only
  --schema-only          # Backup schema only
  --keep-days DAYS       # Retention period for cleanup
```

#### Examples

```bash
# Create full backup
./backup-restore.sh backup

# Create compressed custom format backup
./backup-restore.sh backup --compress --format custom

# Backup data only
./backup-restore.sh backup --data-only

# List available backups
./backup-restore.sh list

# Restore from specific backup
./backup-restore.sh restore --file backups/backup_20240115_143022.dump

# Clean up backups older than 7 days
./backup-restore.sh cleanup --keep-days 7
```

## Database Schema

### Core Tables

#### `origami`

Main table storing origami information:

- `id` - Primary key (BIGSERIAL)
- `origami_id` - External identifier (VARCHAR, UNIQUE)
- `name` - Origami name (VARCHAR, NOT NULL)
- `description` - Description (TEXT)
- `image_url` - Image URL (VARCHAR)
- `vote_count` - Vote count (INTEGER, DEFAULT 0)
- `active` - Active status (BOOLEAN, DEFAULT true)
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp
- `version` - Optimistic locking version

#### `origami_audit`

Audit trail for all origami changes:

- `id` - Primary key
- `origami_id` - Reference to origami record
- `operation` - Operation type (INSERT, UPDATE, DELETE)
- `old_values` - Previous values (JSONB)
- `new_values` - New values (JSONB)
- `changed_by` - User who made the change
- `changed_at` - Change timestamp
- `session_id` - Session identifier
- `ip_address` - Client IP address

#### `sync_history`

Synchronization tracking:

- `id` - Primary key
- `sync_type` - Type of synchronization
- `records_processed` - Number of records processed
- `records_updated` - Number of records updated
- `records_created` - Number of records created
- `records_deactivated` - Number of records deactivated
- `sync_status` - Synchronization status
- `error_message` - Error details if failed
- `sync_duration_ms` - Duration in milliseconds
- `created_at` - Sync timestamp

#### `application_metrics`

Application performance metrics:

- `id` - Primary key
- `metric_name` - Metric name
- `metric_value` - Metric value
- `metric_type` - Metric type (COUNTER, GAUGE, HISTOGRAM)
- `tags` - Additional metadata (JSONB)
- `recorded_at` - Recording timestamp

#### `health_check_log`

Database health monitoring:

- `id` - Primary key
- `check_name` - Health check name
- `status` - Health status (HEALTHY, DEGRADED, UNHEALTHY)
- `response_time_ms` - Response time
- `details` - Check details (JSONB)
- `checked_at` - Check timestamp

### Views and Functions

#### `origami_stats` View

Provides easy access to origami statistics including vote rankings and popularity levels.

#### `vote_statistics` Materialized View

Performance-optimized view for vote statistics, refreshed periodically.

#### Key Functions

- `upsert_origami_from_catalogue()` - Sync data from catalogue service
- `deactivate_missing_origami()` - Deactivate removed origami
- `get_sync_statistics()` - Get synchronization statistics
- `log_sync_event()` - Log synchronization events
- `perform_database_health_check()` - Database health monitoring
- `cleanup_old_data()` - Data retention management
- `search_origami()` - Full-text search functionality
- `refresh_vote_statistics()` - Refresh materialized views
- `reset_seed_data()` - Reset development data
- `generate_random_votes()` - Generate test vote data

## Development Workflow

### 1. Creating New Migrations

1. Create a new migration file following the naming convention:

   ```
   V{version}__{description}.sql
   ```

   Example: `V5__Add_user_preferences.sql`

2. Write the migration SQL with proper error handling:

   ```sql
   -- Migration V5: Add user preferences
   CREATE TABLE IF NOT EXISTS user_preferences (
       id BIGSERIAL PRIMARY KEY,
       user_id VARCHAR(100) NOT NULL,
       preferences JSONB NOT NULL DEFAULT '{}',
       created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   -- Add indexes
   CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

   -- Log migration
   INSERT INTO sync_history (sync_type, sync_status, error_message)
   VALUES ('MIGRATION_V5', 'SUCCESS', 'Added user preferences table');
   ```

3. Test the migration:
   ```bash
   ./migrate.sh migrate --target 5 --dry-run
   ./migrate.sh migrate --target 5
   ./migrate.sh validate
   ```

### 2. Testing Migrations

1. **Unit Testing**: Test individual migration scripts
2. **Integration Testing**: Test complete migration flow
3. **Rollback Testing**: Ensure data integrity during rollbacks
4. **Performance Testing**: Verify migration performance on large datasets

### 3. Production Deployment

1. **Backup**: Always create a backup before migration

   ```bash
   ./backup-restore.sh backup --compress
   ```

2. **Validate**: Ensure migrations are valid

   ```bash
   ./migrate.sh validate
   ```

3. **Migrate**: Run migrations with monitoring

   ```bash
   ./migrate.sh migrate --verbose
   ```

4. **Verify**: Check migration status and data integrity
   ```bash
   ./migrate.sh info
   SELECT * FROM get_sync_statistics();
   ```

## Troubleshooting

### Common Issues

#### Migration Fails

1. Check database connectivity
2. Verify user permissions
3. Review migration logs
4. Use `flyway:repair` if schema history is corrupted

#### Performance Issues

1. Monitor migration duration
2. Check for blocking queries
3. Consider maintenance windows for large migrations
4. Use `--verbose` flag for detailed logging

#### Data Consistency Issues

1. Use the audit trail to track changes
2. Run data validation queries
3. Check sync history for errors
4. Use backup/restore for recovery

### Useful Queries

```sql
-- Check migration status
SELECT * FROM flyway_schema_history ORDER BY installed_on DESC;

-- View recent sync events
SELECT * FROM sync_history ORDER BY created_at DESC LIMIT 10;

-- Check audit trail
SELECT * FROM origami_audit WHERE changed_at > CURRENT_TIMESTAMP - INTERVAL '1 hour';

-- Get database statistics
SELECT * FROM get_sync_statistics();

-- Check health status
SELECT * FROM perform_database_health_check();

-- View vote statistics
SELECT * FROM vote_statistics;
```

## Best Practices

1. **Always backup before migrations**
2. **Test migrations in development first**
3. **Use transactions for data migrations**
4. **Include rollback procedures**
5. **Monitor migration performance**
6. **Document schema changes**
7. **Use meaningful migration names**
8. **Validate data after migrations**
9. **Keep migrations idempotent**
10. **Regular cleanup of old data**

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review migration logs
3. Consult the Flyway documentation
4. Contact the development team
