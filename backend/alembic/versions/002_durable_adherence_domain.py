"""Add durable dose, call, retry, consent, and delivery state.

This migration is additive for databases that already use the legacy Nalam
schema.  New installations are created by revision 001 from the current ORM
metadata and therefore safely no-op here.
"""

from alembic import op
import sqlalchemy as sa


revision = "002_durable_adherence_domain"
down_revision = "001_spec_field_renames"
branch_labels = None
depends_on = None


def _columns(bind: sa.Connection, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _create_enum_types(bind: sa.Connection) -> None:
    if bind.dialect.name != "postgresql":
        return
    for name, values in {
        "consent_status_enum": ("pending", "granted", "withdrawn"),
        "dose_status_enum": (
            "scheduled",
            "taken",
            "missed",
            "no_answer",
            "side_effect",
            "stock_out",
            "callback_requested",
            "unknown",
            "cancelled",
        ),
        "call_status_enum": (
            "scheduled",
            "initiated",
            "ringing",
            "answered",
            "in_progress",
            "completed",
            "no_answer",
            "busy",
            "failed",
            "cancelled",
            "disconnected",
            "function_call_failed",
        ),
        "retry_status_enum": ("pending", "claimed", "completed", "cancelled", "failed"),
        "delivery_status_enum": (
            "pending",
            "sending",
            "sent",
            "delivered",
            "failed",
            "retry_scheduled",
            "resolved",
        ),
    }.items():
        sa.Enum(*values, name=name, native_enum=True).create(bind, checkfirst=True)


def _add_column_if_missing(bind: sa.Connection, table: str, column: sa.Column) -> None:
    if column.name not in _columns(bind, table):
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    _create_enum_types(bind)

    _add_column_if_missing(
        bind,
        "patients",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
    )
    _add_column_if_missing(
        bind,
        "patients",
        sa.Column(
            "consent_status",
            sa.Enum("pending", "granted", "withdrawn", name="consent_status_enum", create_type=False),
            nullable=False,
            server_default="pending",
        ),
    )
    _add_column_if_missing(bind, "patients", sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(
        bind,
        "patients",
        sa.Column("call_window_start_minute", sa.Integer(), nullable=False, server_default="480"),
    )
    _add_column_if_missing(
        bind,
        "patients",
        sa.Column("call_window_end_minute", sa.Integer(), nullable=False, server_default="1200"),
    )
    _add_column_if_missing(
        bind,
        "patients",
        sa.Column("demo_only", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    _add_column_if_missing(bind, "medications", sa.Column("stock_quantity", sa.Integer(), nullable=True))
    _add_column_if_missing(
        bind,
        "medications",
        sa.Column("refill_threshold", sa.Integer(), nullable=False, server_default="5"),
    )
    _add_column_if_missing(
        bind,
        "medications",
        sa.Column("units_per_dose", sa.Integer(), nullable=False, server_default="1"),
    )

    _add_column_if_missing(bind, "adherence_logs", sa.Column("scheduled_dose_id", sa.Uuid(), nullable=True))
    _add_column_if_missing(bind, "adherence_logs", sa.Column("call_record_id", sa.Uuid(), nullable=True))
    _add_column_if_missing(
        bind,
        "adherence_logs",
        sa.Column("taken_late", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(bind, "adherence_logs", sa.Column("side_effect_severity", sa.String(length=16), nullable=True))
    _add_column_if_missing(
        bind,
        "adherence_logs",
        sa.Column("stock_out", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(
        bind,
        "adherence_logs",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="voice"),
    )
    _add_column_if_missing(bind, "adherence_logs", sa.Column("idempotency_key", sa.String(length=255), nullable=True))

    _add_column_if_missing(bind, "alerts", sa.Column("scheduled_dose_id", sa.Uuid(), nullable=True))
    _add_column_if_missing(bind, "alerts", sa.Column("call_record_id", sa.Uuid(), nullable=True))
    _add_column_if_missing(bind, "alerts", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    _add_column_if_missing(
        bind,
        "alerts",
        sa.Column(
            "delivery_status",
            sa.Enum(
                "pending",
                "sending",
                "sent",
                "delivered",
                "failed",
                "retry_scheduled",
                "resolved",
                name="delivery_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
    )
    _add_column_if_missing(bind, "alerts", sa.Column("delivery_attempt_count", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing(bind, "alerts", sa.Column("provider_message_id", sa.String(length=255), nullable=True))
    _add_column_if_missing(bind, "alerts", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(bind, "alerts", sa.Column("delivery_failure_reason", sa.Text(), nullable=True))
    _add_column_if_missing(bind, "alerts", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))

    # Create all new durable tables from the single source of truth. Existing
    # tables are not rewritten by create_all, so this is safe for upgrades.
    from app.models import Base

    Base.metadata.create_all(bind=bind)

    # Nullable event keys permit legacy rows while preventing duplicate keys
    # for all newly processed events.
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("adherence_logs")}
    if "uq_adherence_logs_idempotency_key" not in existing_indexes:
        op.create_index(
            "uq_adherence_logs_idempotency_key",
            "adherence_logs",
            ["idempotency_key"],
            unique=True,
        )
    existing_alert_indexes = {index["name"] for index in inspector.get_indexes("alerts")}
    if "uq_alerts_idempotency_key" not in existing_alert_indexes:
        op.create_index("uq_alerts_idempotency_key", "alerts", ["idempotency_key"], unique=True)

    if bind.dialect.name == "postgresql":
        foreign_keys = {
            (foreign_key["constrained_table"], tuple(foreign_key["constrained_columns"]))
            for table in ("adherence_logs", "alerts")
            for foreign_key in sa.inspect(bind).get_foreign_keys(table)
        }
        if ("adherence_logs", ("scheduled_dose_id",)) not in foreign_keys:
            op.create_foreign_key(
                "fk_adherence_logs_scheduled_dose",
                "adherence_logs",
                "scheduled_doses",
                ["scheduled_dose_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if ("adherence_logs", ("call_record_id",)) not in foreign_keys:
            op.create_foreign_key(
                "fk_adherence_logs_call_record",
                "adherence_logs",
                "call_records",
                ["call_record_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if ("alerts", ("scheduled_dose_id",)) not in foreign_keys:
            op.create_foreign_key(
                "fk_alerts_scheduled_dose",
                "alerts",
                "scheduled_doses",
                ["scheduled_dose_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if ("alerts", ("call_record_id",)) not in foreign_keys:
            op.create_foreign_key(
                "fk_alerts_call_record",
                "alerts",
                "call_records",
                ["call_record_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("retry_jobs", "call_records", "scheduled_doses"):
        if sa.inspect(bind).has_table(table):
            op.drop_table(table)

    for table, names in {
        "patients": (
            "timezone",
            "consent_status",
            "consent_at",
            "call_window_start_minute",
            "call_window_end_minute",
            "demo_only",
        ),
        "medications": ("stock_quantity", "refill_threshold", "units_per_dose"),
        "adherence_logs": (
            "scheduled_dose_id",
            "call_record_id",
            "taken_late",
            "side_effect_severity",
            "stock_out",
            "source",
            "idempotency_key",
        ),
        "alerts": (
            "scheduled_dose_id",
            "call_record_id",
            "idempotency_key",
            "delivery_status",
            "delivery_attempt_count",
            "provider_message_id",
            "delivered_at",
            "delivery_failure_reason",
            "resolved_at",
        ),
    }.items():
        for name in names:
            if name in _columns(bind, table):
                op.drop_column(table, name)
