from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE product_status AS ENUM ('DRAFT', 'PUBLISHED', 'HIDDEN')")
    op.execute(
        """
        CREATE TABLE products (
            id          uuid PRIMARY KEY,
            title       varchar(255)   NOT NULL,
            description text,
            price       numeric(12,2)  NOT NULL,
            currency    varchar(3)     NOT NULL DEFAULT 'RUB',
            seller_id   uuid           NOT NULL,
            status      product_status NOT NULL,
            created_at  timestamptz    NOT NULL DEFAULT now(),
            updated_at  timestamptz    NOT NULL DEFAULT now(),
            CONSTRAINT products_price_positive CHECK (price > 0)
        )
        """
    )
    op.execute("CREATE INDEX idx_products_seller_id ON products (seller_id)")
    op.execute("CREATE INDEX idx_products_status ON products (status)")


def downgrade() -> None:
    op.execute("DROP TABLE products")
    op.execute("DROP TYPE product_status")
