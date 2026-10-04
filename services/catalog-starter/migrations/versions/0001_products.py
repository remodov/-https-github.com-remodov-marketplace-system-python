"""таблица товаров"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE products (
            id      uuid PRIMARY KEY,
            title   varchar(255)  NOT NULL,
            price   numeric(12,2) NOT NULL,
            stock   int           NOT NULL,
            version bigint        NOT NULL DEFAULT 0
        )
        """
    )
    op.execute("CREATE INDEX idx_products_title ON products (title)")


def downgrade() -> None:
    op.execute("DROP TABLE products")
