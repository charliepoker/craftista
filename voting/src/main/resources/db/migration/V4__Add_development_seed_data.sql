-- Migration V4: Development Environment Seed Data
-- This migration adds comprehensive seed data for development and testing environments.
-- It includes additional origami entries, sample votes, and test scenarios.

-- Insert additional origami entries for development testing
INSERT INTO origami (origami_id, name, description, image_url, vote_count, active) VALUES
-- Additional origami from the catalogue service
('6', 'Origami Elephant', 'Majestic and wise, this Origami Elephant captures the gentle giant''s noble presence with carefully folded ears and a graceful trunk.', '/static/images/origami/004-elephant.png', 15, true),
('7', 'Origami Rabbit', 'Hop into a world of charm with this adorable Origami Rabbit, featuring perky ears and a fluffy tail that brings joy to any space.', '/static/images/origami/006-rabbit.png', 8, true),
('8', 'Origami Dove', 'Symbol of peace and serenity, this Origami Dove spreads its wings in graceful flight, embodying hope and tranquility.', '/static/images/origami/007-dove.png', 22, true),
('9', 'Origami Dinosaur', 'Roar into prehistoric times with this fierce Origami Dinosaur, bringing ancient creatures to life through the art of paper folding.', '/static/images/origami/013-dinosaur.png', 31, true),
('10', 'Origami Bird', 'Soar to new heights with this elegant Origami Bird, its wings spread wide in eternal flight, capturing the essence of freedom.', '/static/images/origami/014-bird.png', 12, true),
('11', 'Origami Penguin', 'Waddle into cuteness with this charming Origami Penguin, dressed in nature''s finest tuxedo and ready for Antarctic adventures.', '/static/images/origami/015-penguin.png', 18, true),
('12', 'Origami Fox', 'Clever and cunning, this Origami Fox showcases the sly beauty of woodland creatures with its pointed ears and bushy tail.', '/static/images/origami/023-fox.png', 25, true),

-- Test entries for various scenarios
('test_1', 'Test Origami Alpha', 'This is a test origami for development purposes - Alpha version.', '/static/images/origami/day1.png', 0, true),
('test_2', 'Test Origami Beta', 'This is a test origami for development purposes - Beta version.', '/static/images/origami/day2.png', 5, true),
('test_3', 'Test Origami Gamma', 'This is a test origami for development purposes - Gamma version.', '/static/images/origami/day3.png', 10, false),
('test_4', 'Test Origami Delta', 'This is a test origami for development purposes - Delta version.', '/static/images/origami/day4.png', 100, true),

-- Special characters and edge case testing
('special_1', 'Origami with "Quotes"', 'Testing origami with special characters: !@#$%^&*()_+-=[]{}|;:,.<>?', '/static/images/origami/day5.png', 3, true),
('unicode_1', 'Origami 折り紙', 'Testing unicode characters in origami names and descriptions: 鶴 (crane) 蛙 (frog)', '/static/images/origami/day6.png', 7, true),
('long_name_1', 'This is an Extremely Long Origami Name That Tests the Maximum Length Limits of the Name Field and How the System Handles Very Long Names', 'This origami has an extremely long name to test system limits.', '/static/images/origami/day7.png', 1, true)

ON CONFLICT (origami_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    image_url = EXCLUDED.image_url,
    vote_count = EXCLUDED.vote_count,
    active = EXCLUDED.active,
    updated_at = CURRENT_TIMESTAMP;

-- Create sample audit entries to test audit functionality
-- Note: These will be created automatically by triggers, but we can simulate some historical data

-- Insert sample metrics for testing
INSERT INTO application_metrics (metric_name, metric_value, metric_type, tags, recorded_at) VALUES
('total_votes_cast', 156, 'COUNTER', '{"source": "seed_data"}', CURRENT_TIMESTAMP - INTERVAL '1 hour'),
('active_users', 25, 'GAUGE', '{"source": "seed_data"}', CURRENT_TIMESTAMP - INTERVAL '30 minutes'),
('database_connections', 8, 'GAUGE', '{"source": "seed_data"}', CURRENT_TIMESTAMP - INTERVAL '15 minutes'),
('response_time_ms', 45.5, 'HISTOGRAM', '{"endpoint": "/api/origami", "method": "GET"}', CURRENT_TIMESTAMP - INTERVAL '5 minutes'),
('error_rate', 0.02, 'GAUGE', '{"service": "voting"}', CURRENT_TIMESTAMP - INTERVAL '2 minutes');

-- Insert sample health check logs
INSERT INTO health_check_log (check_name, status, response_time_ms, details, checked_at) VALUES
('database_connectivity', 'HEALTHY', 12, '{"connections": 5, "tables": 8}', CURRENT_TIMESTAMP - INTERVAL '10 minutes'),
('database_connectivity', 'HEALTHY', 15, '{"connections": 6, "tables": 8}', CURRENT_TIMESTAMP - INTERVAL '5 minutes'),
('database_connectivity', 'HEALTHY', 8, '{"connections": 4, "tables": 8}', CURRENT_TIMESTAMP - INTERVAL '1 minute');

-- Insert sample sync history for testing
INSERT INTO sync_history (sync_type, records_processed, records_updated, records_created, records_deactivated, sync_status, sync_duration_ms, created_at) VALUES
('CATALOGUE_SYNC', 12, 3, 2, 0, 'SUCCESS', 1250, CURRENT_TIMESTAMP - INTERVAL '2 hours'),
('CATALOGUE_SYNC', 12, 1, 0, 1, 'SUCCESS', 980, CURRENT_TIMESTAMP - INTERVAL '1 hour'),
('CATALOGUE_SYNC', 15, 2, 3, 0, 'SUCCESS', 1100, CURRENT_TIMESTAMP - INTERVAL '30 minutes'),
('MANUAL_SYNC', 5, 1, 0, 0, 'SUCCESS', 450, CURRENT_TIMESTAMP - INTERVAL '15 minutes');

-- Create test scenarios for different vote distributions
UPDATE origami SET vote_count = 
    CASE origami_id
        WHEN '1' THEN 45   -- High popularity
        WHEN '2' THEN 32   -- High popularity  
        WHEN '3' THEN 28   -- Medium-high popularity
        WHEN '4' THEN 19   -- Medium popularity
        WHEN '5' THEN 15   -- Medium popularity
        WHEN '6' THEN 12   -- Medium popularity
        WHEN '7' THEN 8    -- Low-medium popularity
        WHEN '8' THEN 5    -- Low popularity
        WHEN '9' THEN 3    -- Low popularity
        WHEN '10' THEN 1   -- Very low popularity
        WHEN '11' THEN 0   -- No votes
        WHEN '12' THEN 0   -- No votes
        ELSE vote_count
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE origami_id IN ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12');

-- Refresh materialized views with new data
REFRESH MATERIALIZED VIEW vote_statistics;

-- Record metrics about the seed data
SELECT record_metric('seed_data_origami_count', (SELECT COUNT(*) FROM origami WHERE active = true), 'GAUGE', '{"type": "seed_data"}');
SELECT record_metric('seed_data_total_votes', (SELECT SUM(vote_count) FROM origami WHERE active = true), 'GAUGE', '{"type": "seed_data"}');

-- Log the seeding completion
INSERT INTO sync_history (sync_type, records_processed, records_created, sync_status, error_message, created_at)
VALUES ('SEED_DATA_V4', (SELECT COUNT(*) FROM origami), (SELECT COUNT(*) FROM origami WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '1 minute'), 'SUCCESS', 'Development seed data inserted successfully', CURRENT_TIMESTAMP);

-- Create a function to reset seed data (useful for testing)
CREATE OR REPLACE FUNCTION reset_seed_data()
RETURNS TABLE (
    action VARCHAR(50),
    affected_rows INTEGER
) AS $$
DECLARE
    deleted_origami INTEGER;
    deleted_metrics INTEGER;
    deleted_health INTEGER;
    deleted_sync INTEGER;
    deleted_audit INTEGER;
BEGIN
    -- Delete test origami (those with origami_id starting with 'test_' or 'special_' or 'unicode_' or 'long_name_')
    DELETE FROM origami 
    WHERE origami_id LIKE 'test_%' 
       OR origami_id LIKE 'special_%' 
       OR origami_id LIKE 'unicode_%' 
       OR origami_id LIKE 'long_name_%';
    GET DIAGNOSTICS deleted_origami = ROW_COUNT;
    
    -- Reset vote counts for main origami to 0
    UPDATE origami SET vote_count = 0, updated_at = CURRENT_TIMESTAMP 
    WHERE origami_id IN ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12');
    
    -- Delete seed metrics
    DELETE FROM application_metrics WHERE tags @> '{"source": "seed_data"}';
    GET DIAGNOSTICS deleted_metrics = ROW_COUNT;
    
    -- Delete seed health checks (keep recent ones)
    DELETE FROM health_check_log WHERE checked_at < CURRENT_TIMESTAMP - INTERVAL '1 hour';
    GET DIAGNOSTICS deleted_health = ROW_COUNT;
    
    -- Delete seed sync history
    DELETE FROM sync_history WHERE sync_type IN ('SEED_DATA_V4', 'MANUAL_SYNC');
    GET DIAGNOSTICS deleted_sync = ROW_COUNT;
    
    -- Delete related audit entries
    DELETE FROM origami_audit WHERE origami_id IN (
        SELECT id FROM origami WHERE origami_id LIKE 'test_%' 
           OR origami_id LIKE 'special_%' 
           OR origami_id LIKE 'unicode_%' 
           OR origami_id LIKE 'long_name_%'
    );
    GET DIAGNOSTICS deleted_audit = ROW_COUNT;
    
    -- Refresh materialized view
    REFRESH MATERIALIZED VIEW vote_statistics;
    
    RETURN QUERY VALUES 
        ('deleted_test_origami', deleted_origami),
        ('deleted_seed_metrics', deleted_metrics),
        ('deleted_old_health_checks', deleted_health),
        ('deleted_seed_sync_history', deleted_sync),
        ('deleted_related_audit', deleted_audit);
        
    -- Log the reset
    INSERT INTO sync_history (sync_type, records_processed, sync_status, error_message)
    VALUES ('RESET_SEED_DATA', deleted_origami + deleted_metrics + deleted_health + deleted_sync + deleted_audit, 'SUCCESS', 'Seed data reset completed');
END;
$$ LANGUAGE plpgsql;

-- Create a function to generate random vote data for testing
CREATE OR REPLACE FUNCTION generate_random_votes(
    p_min_votes INTEGER DEFAULT 0,
    p_max_votes INTEGER DEFAULT 100
) RETURNS TABLE (
    origami_id VARCHAR(50),
    old_votes INTEGER,
    new_votes INTEGER
) AS $$
BEGIN
    RETURN QUERY
    UPDATE origami 
    SET vote_count = floor(random() * (p_max_votes - p_min_votes + 1) + p_min_votes)::INTEGER,
        updated_at = CURRENT_TIMESTAMP
    WHERE active = true
    RETURNING origami.origami_id, 0 as old_votes, origami.vote_count as new_votes;
    
    -- Refresh materialized view after vote changes
    REFRESH MATERIALIZED VIEW vote_statistics;
    
    -- Log the vote generation
    INSERT INTO sync_history (sync_type, records_processed, sync_status, error_message)
    VALUES ('GENERATE_RANDOM_VOTES', (SELECT COUNT(*) FROM origami WHERE active = true), 'SUCCESS', 'Random votes generated for testing');
END;
$$ LANGUAGE plpgsql;

-- Final log entry
SELECT record_metric('migration_v4_completed', 1, 'COUNTER', jsonb_build_object('version', 'V4', 'timestamp', CURRENT_TIMESTAMP, 'seed_records', (SELECT COUNT(*) FROM origami)));

COMMIT;