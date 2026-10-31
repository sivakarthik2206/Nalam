"""spec field renames

Revision ID: 001_spec_field_renames
Revises:
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = '001_spec_field_renames'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('patients'):
        # The original repository had no initial migration.  On a new
        # installation create the complete current model graph; revision 002
        # remains responsible for upgrading databases created from the legacy
        # pre-migration schema.
        from app.models import Base

        Base.metadata.create_all(bind=bind)
        return

    table_columns = {
        table: {column['name'] for column in sa.inspect(bind).get_columns(table)}
        for table in ('patients', 'adherence_logs', 'medications')
        if sa.inspect(bind).has_table(table)
    }

    # patients: rename family_contact_phone -> family_whatsapp
    if 'family_contact_phone' in table_columns.get('patients', set()) and 'family_whatsapp' not in table_columns.get('patients', set()):
        op.alter_column('patients', 'family_contact_phone', new_column_name='family_whatsapp')

    # adherence_logs: rename response -> outcome
    if 'response' in table_columns.get('adherence_logs', set()) and 'outcome' not in table_columns.get('adherence_logs', set()):
        op.alter_column('adherence_logs', 'response', new_column_name='outcome')

    # Convert stored values from lowercase to UPPERCASE canonical
    if 'outcome' in table_columns.get('adherence_logs', set()) or 'response' in table_columns.get('adherence_logs', set()):
        op.execute("""
            UPDATE adherence_logs SET outcome =
              CASE outcome
                WHEN 'taken' THEN 'TAKEN'
                WHEN 'not_taken' THEN 'MISSED'
                WHEN 'missed' THEN 'MISSED'
                WHEN 'side_effect' THEN 'SIDE_EFFECT'
                WHEN 'no_answer' THEN 'NO_ANSWER'
                WHEN 'stock_out' THEN 'STOCK_OUT'
                WHEN 'callback_requested' THEN 'CALLBACK_REQUESTED'
                WHEN 'rescheduled' THEN 'CALLBACK_REQUESTED'
                ELSE UPPER(outcome)
              END
        """)

    # Update the PostgreSQL enum type to use new UPPERCASE values
    # (add new values first, then remove old ones via a workaround)
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TYPE adherence_response_enum ADD VALUE IF NOT EXISTS 'TAKEN'")
        op.execute("ALTER TYPE adherence_response_enum ADD VALUE IF NOT EXISTS 'MISSED'")
        op.execute("ALTER TYPE adherence_response_enum ADD VALUE IF NOT EXISTS 'SIDE_EFFECT'")
        op.execute("ALTER TYPE adherence_response_enum ADD VALUE IF NOT EXISTS 'NO_ANSWER'")
        op.execute("ALTER TYPE adherence_response_enum ADD VALUE IF NOT EXISTS 'STOCK_OUT'")
        op.execute("ALTER TYPE adherence_response_enum ADD VALUE IF NOT EXISTS 'CALLBACK_REQUESTED'")

    # Add new columns to adherence_logs
    existing_log_columns = table_columns.get('adherence_logs', set())
    if 'notes' not in existing_log_columns:
        op.add_column('adherence_logs', sa.Column('notes', sa.Text(), nullable=True))
    if 'retry_scheduled' not in existing_log_columns:
        op.add_column('adherence_logs', sa.Column('retry_scheduled', sa.Boolean(), nullable=False, server_default='false'))

    # Backfill notes from side_effect_details
    if 'notes' not in existing_log_columns:
        op.execute("UPDATE adherence_logs SET notes = side_effect_details WHERE side_effect_details IS NOT NULL")

    # Backfill retry_scheduled from follow_up_needed (if already scheduled)
    if 'retry_scheduled' not in existing_log_columns:
        op.execute("UPDATE adherence_logs SET retry_scheduled = follow_up_needed WHERE follow_up_needed IS NOT NULL AND follow_up_completed = true")

    # medications: rename meal_relation -> meal_timing
    if 'meal_relation' in table_columns.get('medications', set()) and 'meal_timing' not in table_columns.get('medications', set()):
        op.alter_column('medications', 'meal_relation', new_column_name='meal_timing')

    # medications: rename prescribed_duration_days -> prescription_duration_days
    if 'prescribed_duration_days' in table_columns.get('medications', set()) and 'prescription_duration_days' not in table_columns.get('medications', set()):
        op.alter_column('medications', 'prescribed_duration_days', new_column_name='prescription_duration_days')


def downgrade():
    op.alter_column('patients', 'family_whatsapp', new_column_name='family_contact_phone')
    op.alter_column('adherence_logs', 'outcome', new_column_name='response')
    op.execute("""
        UPDATE adherence_logs SET response =
          CASE response
            WHEN 'TAKEN' THEN 'taken'
            WHEN 'MISSED' THEN 'not_taken'
            WHEN 'SIDE_EFFECT' THEN 'side_effect'
            WHEN 'NO_ANSWER' THEN 'no_answer'
            WHEN 'STOCK_OUT' THEN 'stock_out'
            WHEN 'CALLBACK_REQUESTED' THEN 'callback_requested'
            ELSE LOWER(response)
          END
    """)
    op.drop_column('adherence_logs', 'notes')
    op.drop_column('adherence_logs', 'retry_scheduled')
    op.alter_column('medications', 'meal_timing', new_column_name='meal_relation')
    op.alter_column('medications', 'prescription_duration_days', new_column_name='prescribed_duration_days')
