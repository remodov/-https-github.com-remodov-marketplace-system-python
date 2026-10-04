"""триграммный индекс для поиска по части названия"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX idx_products_title_trgm ON products USING gin (title gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX idx_products_title_trgm")
