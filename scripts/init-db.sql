-- PostgreSQL initialisation script
-- Runs once on first container start (via docker-entrypoint-initdb.d)

-- Enable uuid-ossp extension for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for GIN trigram indexes (future full-text search)

-- Create a custom GUC namespace for tenant context (used by Row-Level Security)
-- This allows SET LOCAL app.current_tenant = '<uuid>' to work without superuser
ALTER DATABASE ats SET app.current_tenant TO '';
