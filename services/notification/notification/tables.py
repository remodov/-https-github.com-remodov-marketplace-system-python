from sqlalchemy import Column, DateTime, MetaData, String, Table, Uuid
from sqlalchemy.dialects import postgresql

metadata = MetaData()

processed_events = Table(
    "processed_events",
    metadata,
    Column("event_id", Uuid, primary_key=True),
    Column("event_type", String(128), nullable=False),
    Column("processed_at", DateTime(timezone=True), nullable=False),
)

notifications = Table(
    "notifications",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("event_id", Uuid, nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("user_id", Uuid, nullable=False),
    Column("channel", String(16), nullable=False),
    Column("template_key", String(128), nullable=False),
    Column("status", String(16), nullable=False),
    Column("payload", postgresql.JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
