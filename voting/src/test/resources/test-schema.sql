-- Test schema initialization for PostgreSQL integration tests
-- This script sets up the database schema and initial data for testcontainers

-- Create the origami table if it doesn't exist
-- (Hibernate will actually create it, but this ensures compatibility)

-- Create indexes for better query performance in tests
-- These will be created by Hibernate, but we can add custom ones here if needed

-- Insert some initial test data if needed for specific tests
-- (Most tests will create their own data, but some shared data can go here)

-- Example: Create a test user or configuration data
-- INSERT INTO test_config (key, value) VALUES ('test_mode', 'true');

-- Set up any PostgreSQL-specific configurations for testing
-- ALTER DATABASE testdb SET timezone TO 'UTC';

-- Create any custom functions or procedures needed for testing
-- (None needed for current tests, but placeholder for future needs)

-- Grant necessary permissions (usually not needed in testcontainers)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO testuser;

-- Log that schema initialization is complete
SELECT 'Test schema initialization completed' AS status;