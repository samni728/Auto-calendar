"""Add onboarding fields and remove the original placeholder hotel data."""

import sqlalchemy as sa
from alembic import op

revision = "20260817_0002"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    user_columns = {column["name"] for column in sa.inspect(connection).get_columns("users")}
    if "job_title" not in user_columns:
        op.add_column(
            "users", sa.Column("job_title", sa.String(length=80), nullable=False, server_default="")
        )
    if "onboarding_completed" not in user_columns:
        op.add_column(
            "users",
            sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    placeholder_workspace_ids = [
        row[0]
        for row in connection.execute(
            sa.text("SELECT id FROM workspaces WHERE name = :name"),
            {"name": "广州栖岸酒店"},
        )
    ]
    demo_titles = (
        "林女士 · 已入住",
        "David · Agoda",
        "退房清洁",
        "空调维护",
        "周先生 · 携程",
    )
    demo_room_codes = ("301", "302", "303", "305", "401", "402", "403", "501")

    for workspace_id in placeholder_workspace_ids:
        connection.execute(
            sa.text(
                "DELETE FROM timeline_events "
                "WHERE workspace_id = :workspace_id AND source_system = 'local' "
                "AND title IN :titles"
            ).bindparams(sa.bindparam("titles", expanding=True)),
            {"workspace_id": workspace_id, "titles": demo_titles},
        )
        room_ids = [
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT id FROM rooms WHERE workspace_id = :workspace_id AND code IN :codes"
                ).bindparams(sa.bindparam("codes", expanding=True)),
                {"workspace_id": workspace_id, "codes": demo_room_codes},
            )
        ]
        if room_ids:
            connection.execute(
                sa.text("UPDATE timeline_events SET room_id = NULL WHERE room_id IN :room_ids").bindparams(
                    sa.bindparam("room_ids", expanding=True)
                ),
                {"room_ids": room_ids},
            )
            connection.execute(
                sa.text("DELETE FROM rooms WHERE id IN :room_ids").bindparams(
                    sa.bindparam("room_ids", expanding=True)
                ),
                {"room_ids": room_ids},
            )
        connection.execute(
            sa.text("UPDATE workspaces SET name = :new_name WHERE id = :workspace_id"),
            {"new_name": "未命名酒店", "workspace_id": workspace_id},
        )

    connection.execute(
        sa.text(
            "UPDATE users SET display_name = :new_name, job_title = '', "
            "onboarding_completed = false "
            "WHERE display_name = :old_name"
        ),
        {
            "new_name": "管理员",
            "old_name": "陈经理",
        },
    )
    connection.execute(
        sa.text(
            "UPDATE workspace_memberships SET role = 'workspace_admin' "
            "WHERE role = 'security_admin'"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed")
    op.drop_column("users", "job_title")
