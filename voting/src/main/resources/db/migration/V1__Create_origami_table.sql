-- Create origami table with enhanced structure for production use
-- This migration creates the main origami table with proper constraints,
-- indexes, and audit fields for the voting service.

CREATE TABLE IF NOT EXISTS origami (
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

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_origami_active ON origami(active);
CREATE INDEX IF NOT EXISTS idx_origami_external_id ON origami(origami_id);
CREATE INDEX IF NOT EXISTS idx_origami_vote_count ON origami(vote_count);
CREATE INDEX IF NOT EXISTS idx_origami_created_at ON origami(created_at);
CREATE INDEX IF NOT EXISTS idx_origami_updated_at ON origami(updated_at);

-- Create composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_origami_active_vote_count ON origami(active, vote_count DESC);
CREATE INDEX IF NOT EXISTS idx_origami_active_created_at ON origami(active, created_at DESC);

-- Add constraints
ALTER TABLE origami ADD CONSTRAINT chk_vote_count_non_negative CHECK (vote_count >= 0);
ALTER TABLE origami ADD CONSTRAINT chk_origami_id_not_empty CHECK (origami_id != '');
ALTER TABLE origami ADD CONSTRAINT chk_name_not_empty CHECK (name != '');

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at on row updates
CREATE TRIGGER update_origami_updated_at 
    BEFORE UPDATE ON origami 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Insert some initial data for testing (optional)
INSERT INTO origami (origami_id, name, description, image_url, vote_count, active) VALUES
('1', 'Origami Crane', 'Behold the delicate elegance of this Origami Crane, rendered in soft pastel hues that lend it an ethereal charm.', '/static/images/origami/001-origami.png', 0, true),
('2', 'Origami Frog', 'Dive into the enchanting realm of the Origami Frog, a captivating representation of the amphibious wonders.', '/static/images/origami/012-origami-8.png', 0, true),
('3', 'Origami Kangaroo', 'Step into the rugged landscapes of the Australian outback with our Origami Kangaroo.', '/static/images/origami/010-origami-6.png', 0, true),
('4', 'Origami Camel', 'Journey into the sun-kissed dunes of the desert with our Origami Camel.', '/static/images/origami/021-camel.png', 0, true),
('5', 'Origami Butterfly', 'Witness the ephemeral beauty of our Origami Butterfly, a delicate creation symbolizing transformation.', '/static/images/origami/017-origami-9.png', 0, true)
ON CONFLICT (origami_id) DO NOTHING;