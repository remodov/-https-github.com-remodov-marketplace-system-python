from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE order_status AS ENUM (
            'DRAFT', 'PENDING_PAYMENT', 'PAID', 'SHIPPED', 'DELIVERED',
            'COMPLETED', 'EXPIRED', 'CANCELLED', 'DISPUTE', 'REFUNDED'
        )
        """
    )
    op.execute(
        """
        CREATE TABLE orders (
            id               uuid PRIMARY KEY,
            customer_id      uuid          NOT NULL,
            seller_id        uuid          NOT NULL,
            status           order_status  NOT NULL,
            currency         char(3)       NOT NULL DEFAULT 'RUB',
            total_amount     numeric(12,2) NOT NULL CHECK (total_amount >= 0),
            shipping_fee     numeric(12,2) NOT NULL CHECK (shipping_fee >= 0),
            shipping_address jsonb         NOT NULL,
            created_at       timestamptz   NOT NULL,
            updated_at       timestamptz   NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE order_items (
            id         uuid PRIMARY KEY,
            order_id   uuid          NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
            product_id uuid          NOT NULL,
            seller_id  uuid          NOT NULL,
            quantity   int           NOT NULL CHECK (quantity > 0 AND quantity <= 999),
            unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0),
            CONSTRAINT order_items_product_seller_unique UNIQUE (order_id, product_id, seller_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_orders_customer_status_created ON orders (customer_id, status, created_at DESC)"
    )
    op.execute("CREATE INDEX idx_orders_seller_status_created ON orders (seller_id, status, created_at DESC)")
    op.execute("CREATE INDEX idx_order_items_product ON order_items (product_id)")


def downgrade() -> None:
    op.execute("DROP TABLE order_items")
    op.execute("DROP TABLE orders")
    op.execute("DROP TYPE order_status")
