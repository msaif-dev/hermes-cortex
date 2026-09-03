-- Initialize development database
-- Creates a read-only user for the agent (least privilege)

-- Create read-only user
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'hermes_readonly') THEN
        CREATE ROLE hermes_readonly WITH LOGIN PASSWORD 'dev_readonly_password';
    END IF;
END
$$;

-- Grant read-only access to all current and future tables
GRANT CONNECT ON DATABASE hermes TO hermes_readonly;
GRANT USAGE ON SCHEMA public TO hermes_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO hermes_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO hermes_readonly;

-- Set statement timeout for the read-only user (30 seconds)
ALTER ROLE hermes_readonly SET statement_timeout = '30s';

-- Create sample tables for development
CREATE TABLE IF NOT EXISTS sample_data (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    value NUMERIC(12, 2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert sample data
INSERT INTO sample_data (category, description, value) VALUES
('revenue', 'Q1 2026 Revenue', 1250000.00),
('revenue', 'Q2 2026 Revenue', 1380000.00),
('revenue', 'Q3 2026 Revenue', 1520000.00),
('expense', 'Q1 2026 Operating Cost', 890000.00),
('expense', 'Q2 2026 Operating Cost', 920000.00),
('expense', 'Q3 2026 Operating Cost', 950000.00)
ON CONFLICT DO NOTHING;
