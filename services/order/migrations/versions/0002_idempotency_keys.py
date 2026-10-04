from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE idempotency_keys (
            idempotency_key varchar(128) PRIMARY KEY,
            request_hash    varchar(64)  NOT NULL,
            order_id        uuid         NOT NULL REFERENCES orders (id),
            created_at      timestamptz  NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX idx_idempotency_keys_created ON idempotency_keys (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE idempotency_keys")
