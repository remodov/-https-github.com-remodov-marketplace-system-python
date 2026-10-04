from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE orders
            ADD COLUMN payment_id   uuid,
            ADD COLUMN paid_at      timestamptz,
            ADD COLUMN shipped_at   timestamptz,
            ADD COLUMN delivered_at timestamptz,
            ADD COLUMN closed_at    timestamptz
        """
    )
    op.execute(
        """
        CREATE INDEX idx_orders_pending_payment_updated ON orders (updated_at)
        WHERE status = 'PENDING_PAYMENT'
        """
    )
    op.execute(
        """
        CREATE TABLE processed_events (
            event_id     uuid PRIMARY KEY,
            event_type   varchar(128) NOT NULL,
            processed_at timestamptz  NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE processed_events")
    op.execute("DROP INDEX idx_orders_pending_payment_updated")
    op.execute(
        """
        ALTER TABLE orders
            DROP COLUMN closed_at,
            DROP COLUMN delivered_at,
            DROP COLUMN shipped_at,
            DROP COLUMN paid_at,
            DROP COLUMN payment_id
        """
    )
