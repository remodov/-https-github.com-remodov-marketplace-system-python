from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE outbox (
            id             uuid PRIMARY KEY,
            aggregate_id   uuid         NOT NULL,
            aggregate_type varchar(64)  NOT NULL,
            event_type     varchar(128) NOT NULL,
            event_version  int          NOT NULL DEFAULT 1,
            payload        jsonb        NOT NULL,
            occurred_at    timestamptz  NOT NULL,
            published_at   timestamptz
        )
        """
    )
    op.execute("CREATE INDEX idx_outbox_unpublished ON outbox (occurred_at) WHERE published_at IS NULL")
    op.execute("CREATE INDEX idx_outbox_aggregate ON outbox (aggregate_id, occurred_at)")


def downgrade() -> None:
    op.execute("DROP TABLE outbox")
