from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE catalog_audit_log (
            id          uuid PRIMARY KEY,
            actor_id    uuid        NOT NULL,
            action      varchar(64) NOT NULL,
            product_id  uuid        NOT NULL,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute("CREATE INDEX idx_catalog_audit_log_product_id ON catalog_audit_log (product_id)")
    op.execute("CREATE INDEX idx_catalog_audit_log_actor_id ON catalog_audit_log (actor_id)")


def downgrade() -> None:
    op.execute("DROP TABLE catalog_audit_log")
