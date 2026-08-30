-- Initialize vector extension for PostgreSQL
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log completion
DO $$
BEGIN
  RAISE NOTICE 'pgvector and uuid extensions initialized successfully.';
END $$;
