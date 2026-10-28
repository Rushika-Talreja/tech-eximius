-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- RLS helper function
CREATE OR REPLACE FUNCTION set_org_id(p_org_id uuid)
  RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  PERFORM set_config('app.org_id', p_org_id::text, true);
END;
$$;
