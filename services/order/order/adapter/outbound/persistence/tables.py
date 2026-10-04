from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, MetaData, Numeric, Table, Uuid
from sqlalchemy.dialects import postgresql

metadata = MetaData()

order_status = postgresql.ENUM(
    "DRAFT",
    "PENDING_PAYMENT",
    "PAID",
    "SHIPPED",
    "DELIVERED",
    "COMPLETED",
    "EXPIRED",
    "CANCELLED",
    "DISPUTE",
    "REFUNDED",
    name="order_status",
    create_type=False,
)

orders = Table(
    "orders",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("customer_id", Uuid, nullable=False),
    Column("seller_id", Uuid, nullable=False),
    Column("status", order_status, nullable=False),
    Column("currency", CHAR(3), nullable=False),
    Column("total_amount", Numeric(12, 2), nullable=False),
    Column("shipping_fee", Numeric(12, 2), nullable=False),
    Column("shipping_address", postgresql.JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

order_items = Table(
    "order_items",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("order_id", Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
    Column("product_id", Uuid, nullable=False),
    Column("seller_id", Uuid, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Numeric(12, 2), nullable=False),
)
