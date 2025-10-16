-- Data migration script for Voting Service
-- This migration provides procedures to sync data from the Catalogue service
-- and handle data consistency between services.

-- Create a function to safely insert or update origami data
CREATE OR REPLACE FUNCTION upsert_origami_from_catalogue(
    p_origami_id VARCHAR(50),
    p_name VARCHAR(255),
    p_description TEXT,
    p_image_url VARCHAR(500)
) RETURNS VOID AS $$
BEGIN
    -- Insert or update origami record
    INSERT INTO origami (origami_id, name, description, image_url, vote_count, active, created_at, updated_at)
    VALUES (p_origami_id, p_name, p_description, p_image_url, 0, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (origami_id) 
    DO UPDATE SET 
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        image_url = EXCLUDED.image_url,
        updated_at = CURRENT_TIMESTAMP
    WHERE origami.name != EXCLUDED.name 
       OR origami.description != EXCLUDED.description 
       OR origami.image_url != EXCLUDED.image_url;
END;
$$ LANGUAGE plpgsql;

-- Create a function to deactivate origami that no longer exist in catalogue
CREATE OR REPLACE FUNCTION deactivate_missing_origami(
    active_origami_ids VARCHAR(50)[]
) RETURNS INTEGER AS $$
DECLARE
    deactivated_count INTEGER;
BEGIN
    -- Deactivate origami that are not in the provided list
    UPDATE origami 
    SET active = false, updated_at = CURRENT_TIMESTAMP
    WHERE active = true 
      AND origami_id != ALL(active_origami_ids);
    
    GET DIAGNOSTICS deactivated_count = ROW_COUNT;
    RETURN deactivated_count;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get synchronization statistics
CREATE OR REPLACE FUNCTION get_sync_statistics()
RETURNS TABLE (
    total_origami INTEGER,
    active_origami INTEGER,
    inactive_origami INTEGER,
    total_votes INTEGER,
    last_sync_time TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INTEGER as total_origami,
        COUNT(CASE WHEN o.active = true THEN 1 END)::INTEGER as active_origami,
        COUNT(CASE WHEN o.active = false THEN 1 END)::INTEGER as inactive_origami,
        COALESCE(SUM(o.vote_count), 0)::INTEGER as total_votes,
        MAX(o.updated_at) as last_sync_time
    FROM origami o;
END;
$$ LANGUAGE plpgsql;

-- Create a table to track synchronization history
CREATE TABLE IF NOT EXISTS sync_history (
    id BIGSERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,
    records_processed INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,
    records_created INTEGER NOT NULL DEFAULT 0,
    records_deactivated INTEGER NOT NULL DEFAULT 0,
    sync_status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    error_message TEXT,
    sync_duration_ms INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create index for sync history queries
CREATE INDEX IF NOT EXISTS idx_sync_history_created_at ON sync_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_history_status ON sync_history(sync_status);

-- Create a function to log synchronization events
CREATE OR REPLACE FUNCTION log_sync_event(
    p_sync_type VARCHAR(50),
    p_records_processed INTEGER DEFAULT 0,
    p_records_updated INTEGER DEFAULT 0,
    p_records_created INTEGER DEFAULT 0,
    p_records_deactivated INTEGER DEFAULT 0,
    p_sync_status VARCHAR(20) DEFAULT 'SUCCESS',
    p_error_message TEXT DEFAULT NULL,
    p_sync_duration_ms INTEGER DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    sync_id BIGINT;
BEGIN
    INSERT INTO sync_history (
        sync_type, records_processed, records_updated, records_created, 
        records_deactivated, sync_status, error_message, sync_duration_ms
    ) VALUES (
        p_sync_type, p_records_processed, p_records_updated, p_records_created,
        p_records_deactivated, p_sync_status, p_error_message, p_sync_duration_ms
    ) RETURNING id INTO sync_id;
    
    RETURN sync_id;
END;
$$ LANGUAGE plpgsql;

-- Create a view for easy access to origami statistics
CREATE OR REPLACE VIEW origami_stats AS
SELECT 
    o.origami_id,
    o.name,
    o.vote_count,
    o.active,
    o.created_at,
    o.updated_at,
    RANK() OVER (ORDER BY o.vote_count DESC) as vote_rank,
    CASE 
        WHEN o.vote_count = 0 THEN 'No votes'
        WHEN o.vote_count BETWEEN 1 AND 10 THEN 'Low popularity'
        WHEN o.vote_count BETWEEN 11 AND 50 THEN 'Medium popularity'
        ELSE 'High popularity'
    END as popularity_level
FROM origami o
WHERE o.active = true;

-- Insert initial comment for migration tracking
INSERT INTO sync_history (sync_type, records_processed, sync_status, error_message)
VALUES ('MIGRATION_V2', 0, 'SUCCESS', 'Database migration V2 completed - Added sync functions and history tracking');

-- Grant necessary permissions (adjust as needed for your environment)
-- GRANT EXECUTE ON FUNCTION upsert_origami_from_catalogue TO voting_app;
-- GRANT EXECUTE ON FUNCTION deactivate_missing_origami TO voting_app;
-- GRANT EXECUTE ON FUNCTION get_sync_statistics TO voting_app;
-- GRANT EXECUTE ON FUNCTION log_sync_event TO voting_app;
-- GRANT SELECT ON origami_stats TO voting_app;
-- GRANT INSERT, SELECT ON sync_history TO voting_app;