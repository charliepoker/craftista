-- PostgreSQL initialization script for Voting database
-- This script creates the voting database schema and initial data

-- Create the voting database (this is handled by POSTGRES_DB environment variable)
-- But we can add additional setup here

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The origami table will be created by Flyway migrations
-- But we can create some initial setup here if needed

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Grant necessary permissions to the voting user
-- (The user is created automatically by the POSTGRES_USER environment variable)

-- Create a sequence for generating unique IDs if needed
CREATE SEQUENCE IF NOT EXISTS global_id_seq START 1000;

-- Log the initialization
DO $$
BEGIN
    RAISE NOTICE 'Voting database initialized successfully';
END $$;