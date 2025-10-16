-- Migration V3: Add audit trails and performance enhancements
-- This migration adds comprehensive audit logging, performance optimizations,
-- and additional database features for production use.

-- Create audit log table for tracking all changes to origami records
CREATE TABLE IF NOT EXISTS origami_audit (
    id BIGSERIAL PRIMARY KEY,
    origami_id BIGINT NOT NULL,
    operation VARCHAR(10) NOT NULL, -- INSERT, UPDATE, DELETE
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT
);

-- Create indexes for audit table
CREATE INDEX IF NOT EXISTS idx_origami_audit_origami_id ON origami_audit(origami_id);
CREATE INDEX IF NOT EXISTS idx_origami_audit_operation ON origami_audit(operation);
CREATE INDEX IF NOT EXISTS idx_origami_audit_changed_at ON origami_audit(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_origami_audit_changed_by ON origami_audit(changed_by);

-- Create function to log audit events
CREATE OR REPLACE FUNCTION log_origami_audit()
RETURNS TRIGGER AS $$
DECLARE
    old_data JSONB;
    new_data JSONB;
BEGIN
    -- Convert OLD and NEW records to JSONB
    IF TG_OP = 'DELETE' THEN
        old_data = to_jsonb(OLD);
        new_data = NULL;
    ELSIF TG_OP = 'INSERT' THEN
        old_data = NULL;
        new_data = to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        old_data = to_jsonb(OLD);
        new_data = to_jsonb(NEW);
    END IF;

    -- Insert audit record
    INSERT INTO origami_audit (
        origami_id, operation, old_values, new_values, 
        changed_by, session_id, ip_address
    ) VALUES (
        COALESCE(NEW.id, OLD.id),
        TG_OP,
        old_data,
        new_data,
        current_setting('application.current_user', true),
        current_setting('application.session_id', true),
        inet(current_setting('application.client_ip', true))
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create audit triggers
CREATE TRIGGER origami_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON origami
    FOR EACH ROW EXECUTE FUNCTION log_origami_audit();

-- Create table for storing application metrics
CREATE TABLE IF NOT EXISTS application_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    metric_type VARCHAR(20) NOT NULL, -- COUNTER, GAUGE, HISTOGRAM
    tags JSONB,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for metrics table
CREATE INDEX IF NOT EXISTS idx_metrics_name_recorded_at ON application_metrics(metric_name, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_type ON application_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded_at ON application_metrics(recorded_at DESC);

-- Create function to record metrics
CREATE OR REPLACE FUNCTION record_metric(
    p_metric_name VARCHAR(100),
    p_metric_value NUMERIC,
    p_metric_type VARCHAR(20) DEFAULT 'GAUGE',
    p_tags JSONB DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO application_metrics (metric_name, metric_value, metric_type, tags)
    VALUES (p_metric_name, p_metric_value, p_metric_type, p_tags);
END;
$$ LANGUAGE plpgsql;

-- Create materialized view for vote statistics (for performance)
CREATE MATERIALIZED VIEW IF NOT EXISTS vote_statistics AS
SELECT 
    COUNT(*) as total_origami,
    COUNT(CASE WHEN active = true THEN 1 END) as active_origami,
    SUM(vote_count) as total_votes,
    AVG(vote_count) as average_votes,
    MAX(vote_count) as max_votes,
    MIN(vote_count) as min_votes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY vote_count) as median_votes,
    COUNT(CASE WHEN vote_count = 0 THEN 1 END) as origami_with_no_votes,
    COUNT(CASE WHEN vote_count > 0 THEN 1 END) as origami_with_votes,
    MAX(updated_at) as last_updated
FROM origami
WHERE active = true;

-- Create unique index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_vote_statistics_unique ON vote_statistics(total_origami);

-- Create function to refresh vote statistics
CREATE OR REPLACE FUNCTION refresh_vote_statistics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY vote_statistics;
    
    -- Record metric about the refresh
    PERFORM record_metric(
        'vote_statistics_refresh',
        1,
        'COUNTER',
        jsonb_build_object('timestamp', CURRENT_TIMESTAMP)
    );
END;
$$ LANGUAGE plpgsql;

-- Create table for database health checks
CREATE TABLE IF NOT EXISTS health_check_log (
    id BIGSERIAL PRIMARY KEY,
    check_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL, -- HEALTHY, DEGRADED, UNHEALTHY
    response_time_ms INTEGER,
    details JSONB,
    checked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for health check log
CREATE INDEX IF NOT EXISTS idx_health_check_name_checked_at ON health_check_log(check_name, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_check_status ON health_check_log(status);

-- Create function for database health check
CREATE OR REPLACE FUNCTION perform_database_health_check()
RETURNS TABLE (
    check_name VARCHAR(100),
    status VARCHAR(20),
    response_time_ms INTEGER,
    details JSONB
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    connection_count INTEGER;
    table_count INTEGER;
    index_count INTEGER;
BEGIN
    start_time := clock_timestamp();
    
    -- Check database connectivity and basic operations
    SELECT COUNT(*) INTO connection_count FROM pg_stat_activity WHERE state = 'active';
    SELECT COUNT(*) INTO table_count FROM information_schema.tables WHERE table_schema = 'public';
    SELECT COUNT(*) INTO index_count FROM pg_indexes WHERE schemaname = 'public';
    
    end_time := clock_timestamp();
    
    RETURN QUERY SELECT 
        'database_connectivity'::VARCHAR(100),
        'HEALTHY'::VARCHAR(20),
        EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER,
        jsonb_build_object(
            'active_connections', connection_count,
            'table_count', table_count,
            'index_count', index_count,
            'timestamp', CURRENT_TIMESTAMP
        );
        
    -- Log the health check
    INSERT INTO health_check_log (check_name, status, response_time_ms, details)
    VALUES (
        'database_connectivity',
        'HEALTHY',
        EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER,
        jsonb_build_object(
            'active_connections', connection_count,
            'table_count', table_count,
            'index_count', index_count
        )
    );
END;
$$ LANGUAGE plpgsql;

-- Create function to clean up old audit and metric data
CREATE OR REPLACE FUNCTION cleanup_old_data(
    p_audit_retention_days INTEGER DEFAULT 90,
    p_metrics_retention_days INTEGER DEFAULT 30,
    p_health_check_retention_days INTEGER DEFAULT 7
) RETURNS TABLE (
    table_name VARCHAR(50),
    deleted_rows INTEGER
) AS $$
DECLARE
    audit_deleted INTEGER;
    metrics_deleted INTEGER;
    health_deleted INTEGER;
BEGIN
    -- Clean up old audit records
    DELETE FROM origami_audit 
    WHERE changed_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * p_audit_retention_days;
    GET DIAGNOSTICS audit_deleted = ROW_COUNT;
    
    -- Clean up old metrics
    DELETE FROM application_metrics 
    WHERE recorded_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * p_metrics_retention_days;
    GET DIAGNOSTICS metrics_deleted = ROW_COUNT;
    
    -- Clean up old health check logs
    DELETE FROM health_check_log 
    WHERE checked_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * p_health_check_retention_days;
    GET DIAGNOSTICS health_deleted = ROW_COUNT;
    
    RETURN QUERY VALUES 
        ('origami_audit'::VARCHAR(50), audit_deleted),
        ('application_metrics'::VARCHAR(50), metrics_deleted),
        ('health_check_log'::VARCHAR(50), health_deleted);
END;
$$ LANGUAGE plpgsql;

-- Create additional indexes for better query performance
-- Note: Trigram indexes require pg_trgm extension which may need superuser privileges
-- Using regular text indexes instead
CREATE INDEX IF NOT EXISTS idx_origami_name_search ON origami(name);
CREATE INDEX IF NOT EXISTS idx_origami_description_search ON origami(description);

-- Enable pg_trgm extension for text search (if not already enabled)
-- Note: This requires superuser privileges, so it might need to be done separately
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create function for full-text search on origami
CREATE OR REPLACE FUNCTION search_origami(
    p_search_term TEXT,
    p_limit INTEGER DEFAULT 10,
    p_offset INTEGER DEFAULT 0
) RETURNS TABLE (
    id BIGINT,
    origami_id VARCHAR(50),
    name VARCHAR(255),
    description TEXT,
    image_url VARCHAR(500),
    vote_count INTEGER,
    similarity_score REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        o.id,
        o.origami_id,
        o.name,
        o.description,
        o.image_url,
        o.vote_count,
        -- Simple relevance scoring without pg_trgm extension
        CASE 
            WHEN o.name ILIKE p_search_term THEN 1.0
            WHEN o.name ILIKE p_search_term || '%' THEN 0.9
            WHEN o.name ILIKE '%' || p_search_term || '%' THEN 0.8
            WHEN COALESCE(o.description, '') ILIKE '%' || p_search_term || '%' THEN 0.6
            ELSE 0.5
        END as similarity_score
    FROM origami o
    WHERE o.active = true
      AND (
          o.name ILIKE '%' || p_search_term || '%'
          OR o.description ILIKE '%' || p_search_term || '%'
      )
    ORDER BY similarity_score DESC, o.vote_count DESC
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Insert migration completion log
INSERT INTO sync_history (sync_type, records_processed, sync_status, error_message)
VALUES ('MIGRATION_V3', 0, 'SUCCESS', 'Added audit trails, performance enhancements, and monitoring capabilities');

-- Record initial metrics
SELECT record_metric('migration_v3_completed', 1, 'COUNTER', jsonb_build_object('version', 'V3', 'timestamp', CURRENT_TIMESTAMP));

-- Refresh the vote statistics materialized view
SELECT refresh_vote_statistics();