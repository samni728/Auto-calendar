"""Add dedicated-calendar settings and per-provider event mirrors."""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "20260817_0003"
down_revision = "20260817_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    connection_columns = {
        column["name"] for column in inspector.get_columns("provider_connections")
    }
    if "sync_mode" not in connection_columns:
        op.add_column(
            "provider_connections",
            sa.Column(
                "sync_mode", sa.String(length=32), nullable=False, server_default="two_way"
            ),
        )
    if "sync_label" not in connection_columns:
        op.add_column(
            "provider_connections",
            sa.Column(
                "sync_label",
                sa.String(length=120),
                nullable=False,
                server_default="Auto Calendar · 酒店订房",
            ),
        )

    if "event_mirrors" not in inspector.get_table_names():
        op.create_table(
            "event_mirrors",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("provider_connection_id", sa.String(length=36), nullable=False),
            sa.Column("external_event_id", sa.Text(), nullable=False),
            sa.Column("external_version", sa.Text(), nullable=True),
            sa.Column("last_synced_hash", sa.String(length=64), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["timeline_events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["provider_connection_id"],
                ["provider_connections.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "event_id", "provider_connection_id", name="uq_event_mirror_connection"
            ),
            sa.UniqueConstraint(
                "provider_connection_id", "external_event_id", name="uq_mirror_external_event"
            ),
        )
        op.create_index("ix_event_mirrors_event_id", "event_mirrors", ["event_id"])
        op.create_index(
            "ix_event_mirrors_provider_connection_id",
            "event_mirrors",
            ["provider_connection_id"],
        )

    rows = connection.execute(
        sa.text(
            "SELECT id, provider_connection_id, external_event_id, external_version "
            "FROM timeline_events WHERE provider_connection_id IS NOT NULL "
            "AND external_event_id IS NOT NULL"
        )
    )
    for event_id, connection_id, external_id, version in rows:
        connection.execute(
            sa.text(
                "INSERT INTO event_mirrors "
                "(id, event_id, provider_connection_id, external_event_id, external_version, "
                "last_synced_hash, is_deleted, created_at, updated_at) "
                "VALUES (:id, :event_id, :connection_id, :external_id, :version, NULL, false, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": str(uuid.uuid4()),
                "event_id": event_id,
                "connection_id": connection_id,
                "external_id": external_id,
                "version": version,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_event_mirrors_provider_connection_id", table_name="event_mirrors")
    op.drop_index("ix_event_mirrors_event_id", table_name="event_mirrors")
    op.drop_table("event_mirrors")
    op.drop_column("provider_connections", "sync_label")
    op.drop_column("provider_connections", "sync_mode")
