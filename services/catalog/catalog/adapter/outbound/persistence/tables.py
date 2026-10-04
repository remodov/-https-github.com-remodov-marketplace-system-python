from sqlalchemy import Column, DateTime, MetaData, Numeric, String, Table, Text, Uuid
from sqlalchemy.dialects import postgresql

metadata = MetaData()

product_status = postgresql.ENUM("DRAFT", "PUBLISHED", "HIDDEN", name="product_status", create_type=False)

products = Table(
    "products",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("title", String(255), nullable=False),
    Column("description", Text),
    Column("price", Numeric(12, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("seller_id", Uuid, nullable=False),
    Column("status", product_status, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

catalog_audit_log = Table(
    "catalog_audit_log",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("actor_id", Uuid, nullable=False),
    Column("action", String(64), nullable=False),
    Column("product_id", Uuid, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("metadata", postgresql.JSONB, nullable=False),
)
