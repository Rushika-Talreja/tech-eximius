"""add finding evidence deferred trigger

Revision ID: 0002_finding_evidence_trigger
Revises: 0001_initial_schema
Create Date: 2026-10-27 22:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_finding_evidence_trigger"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION check_finding_has_evidence() RETURNS TRIGGER AS $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM finding_evidence WHERE finding_id = NEW.id) THEN
            RAISE EXCEPTION 'Finding % must have at least one evidence row', NEW.id;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_finding_evidence_required ON findings;
        CREATE CONSTRAINT TRIGGER trg_finding_evidence_required
        AFTER INSERT OR UPDATE ON findings
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION check_finding_has_evidence();
        """)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("""
        DROP TRIGGER IF EXISTS trg_finding_evidence_required ON findings;
        DROP FUNCTION IF EXISTS check_finding_has_evidence();
        """)

