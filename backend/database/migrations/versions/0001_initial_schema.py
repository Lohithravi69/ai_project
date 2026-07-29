"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-07
"""

from __future__ import annotations

from alembic import op

from backend.config import get_settings
from backend.database.base import Base
from backend.database import models  # noqa: F401 - ensure all tables are registered

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    Base.metadata.create_all(bind=connection)


def downgrade() -> None:
    connection = op.get_bind()
    Base.metadata.drop_all(bind=connection)
