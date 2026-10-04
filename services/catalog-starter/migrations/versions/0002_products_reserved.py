"""резерв отдельно от остатка"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE products ADD COLUMN reserved int NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE products DROP COLUMN reserved")
