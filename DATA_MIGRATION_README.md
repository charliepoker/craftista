# Data Migration Guide

This document provides instructions for migrating existing data to the enhanced database models implemented in task 3.

## Overview

The enhanced data models provide:

### MongoDB (Catalogue Service)

- **Flexible Product Model**: Pydantic-based validation with flexible attributes
- **Automatic Indexing**: Performance-optimized indexes for search and filtering
- **Schema Validation**: MongoDB-level validation rules
- **Migration Support**: Automated migration from JSON data

### PostgreSQL (Voting Service)

- **Enhanced Origami Entity**: JPA annotations with proper constraints
- **Audit Fields**: Creation and update tracking with versioning
- **Migration Scripts**: Flyway-based schema migrations
- **Sync Functions**: Database functions for data synchronization

## Migration Process

### 1. Catalogue Service (MongoDB)

#### Prerequisites

- MongoDB instance running
- Python environment with required dependencies
- Access to existing `products.json` file

#### Running the Migration

```bash
# Navigate to catalogue directory
cd catalogue

# Set environment variables
export MONGODB_URL="mongodb://catalogue_user:catalogue_pass@localhost:27017/catalogue"
export MONGODB_DATABASE="catalogue"
export JSON_FILE_PATH="products.json"

# Dry run (validate without inserting)
export DRY_RUN="true"
python migrate_data.py

# Actual migration
export DRY_RUN="false"
python migrate_data.py
```

#### Migration Features

- **Data Validation**: Pydantic model validation before insertion
- **Duplicate Prevention**: Checks for existing products by name
- **Tag Generation**: Automatic tag extraction from product names
- **Attribute Mapping**: Intelligent attribute assignment based on product type
- **Error Handling**: Comprehensive error logging and recovery

### 2. Voting Service (PostgreSQL)

#### Prerequisites

- PostgreSQL instance running
- Java application with Spring Boot
- Flyway migrations enabled

#### Database Migration

The database schema is automatically migrated using Flyway:

```sql
-- V1__Create_origami_table.sql (already applied)
-- Creates the enhanced origami table with indexes and constraints

-- V2__Data_migration_from_catalogue.sql (new)
-- Adds synchronization functions and history tracking
```

#### Data Synchronization

Use the `DataMigrationService` to sync data from the Catalogue service:

```java
@Autowired
private DataMigrationService migrationService;

// Initial migration
MigrationStats stats = migrationService.performInitialMigration();

// Incremental synchronization
MigrationStats syncStats = migrationService.performIncrementalSync();

// Get statistics
Map<String, Object> statistics = migrationService.getSyncStatistics();
```

## Database Schema Details

### MongoDB Product Schema

```javascript
{
  "_id": ObjectId,
  "name": String (required, 1-255 chars),
  "description": String (optional, max 2000 chars),
  "image_url": String (optional),
  "price": Number (optional, >= 0),
  "category": String (optional, max 100 chars),
  "tags": [String] (array of lowercase strings),
  "attributes": Object (flexible key-value pairs),
  "active": Boolean (default: true),
  "featured": Boolean (default: false),
  "inventory_count": Number (optional, >= 0),
  "created_at": Date (auto-generated),
  "updated_at": Date (auto-updated)
}
```

### PostgreSQL Origami Schema

```sql
CREATE TABLE origami (
    id BIGSERIAL PRIMARY KEY,
    origami_id VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    image_url VARCHAR(500),
    vote_count INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version BIGINT DEFAULT 0
);
```

## Indexes and Performance

### MongoDB Indexes

- Text search: `{name: "text", description: "text"}`
- Category filtering: `{category: 1, active: 1}`
- Tag queries: `{tags: 1}`
- Featured products: `{featured: 1, active: 1}`
- Recent products: `{created_at: -1}`
- Price filtering: `{price: 1, active: 1}`
- Stock filtering: `{inventory_count: 1, active: 1}`

### PostgreSQL Indexes

- Active status: `idx_origami_active`
- External ID: `idx_origami_external_id`
- Vote count: `idx_origami_vote_count`
- Creation date: `idx_origami_created_at`
- Composite: `idx_origami_active_vote_count`, `idx_origami_active_created_at`

## Validation Rules

### Product Validation (MongoDB)

- Name: Required, 1-255 characters, trimmed
- Price: Non-negative number
- Inventory: Non-negative integer
- Tags: Lowercase, unique, no empty strings
- Updated timestamp: Auto-set on changes

### Origami Validation (PostgreSQL)

- Origami ID: Required, unique, max 50 characters
- Name: Required, max 255 characters
- Vote count: Non-negative integer
- Active status: Required boolean
- Version: Optimistic locking support

## Monitoring and Maintenance

### Migration Monitoring

- Check `sync_history` table for migration events
- Use `get_sync_statistics()` function for current state
- Monitor application logs for migration errors

### Data Consistency

- Regular synchronization between services
- Automatic deactivation of removed products
- Conflict resolution for concurrent updates

### Performance Monitoring

- Index usage statistics
- Query performance metrics
- Connection pool monitoring

## Troubleshooting

### Common Issues

1. **Connection Failures**

   - Verify database URLs and credentials
   - Check network connectivity
   - Ensure databases are running

2. **Validation Errors**

   - Check data format in source files
   - Verify required fields are present
   - Review validation error messages

3. **Synchronization Issues**
   - Check catalogue service availability
   - Verify API endpoint responses
   - Review sync history for errors

### Recovery Procedures

1. **Failed Migration**

   - Check error logs for specific issues
   - Run dry-run mode to validate data
   - Fix data issues and retry

2. **Data Inconsistency**
   - Run incremental sync to update changes
   - Check sync statistics for discrepancies
   - Manual data verification if needed

## Best Practices

1. **Before Migration**

   - Backup existing databases
   - Test migration in development environment
   - Verify all dependencies are available

2. **During Migration**

   - Monitor progress and error logs
   - Run in dry-run mode first
   - Process data in batches for large datasets

3. **After Migration**
   - Verify data integrity
   - Test application functionality
   - Set up regular synchronization schedule

## Support

For issues or questions regarding the migration process:

1. Check application logs for detailed error messages
2. Review this documentation for troubleshooting steps
3. Consult the database-specific documentation for advanced issues
