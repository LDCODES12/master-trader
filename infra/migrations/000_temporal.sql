-- Ensure Temporal can use the shared Postgres instance

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'temporal') THEN
        CREATE ROLE temporal LOGIN PASSWORD 'temporal';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal') THEN
        CREATE DATABASE temporal OWNER temporal;
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal_visibility') THEN
        CREATE DATABASE temporal_visibility OWNER temporal;
    END IF;
END$$;


