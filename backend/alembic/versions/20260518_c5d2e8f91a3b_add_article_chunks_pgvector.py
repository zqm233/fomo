"""add article_chunks pgvector table

Revision ID: c5d2e8f91a3b
Revises: a3b7c9d1e2f4
Create Date: 2026-05-18

将向量存储从 ChromaDB 迁移到 PostgreSQL pgvector。
新增 article_chunks 表，含 1024 维 embedding 列与 HNSW cosine 索引。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5d2e8f91a3b"
down_revision: Union[str, None] = "a3b7c9d1e2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "article_chunks",
        sa.Column("id",             sa.String(36),  nullable=False),
        sa.Column("chunk_id",       sa.String(120), nullable=False),
        sa.Column("article_id",     sa.String(36),  nullable=False),
        sa.Column("source_id",      sa.String(36),  nullable=False),
        sa.Column("content",        sa.Text,        nullable=False),
        sa.Column("embedding",      sa.Text,        nullable=True),   # placeholder; real type set below
        sa.Column("chunk_index",    sa.Integer,     nullable=False, server_default="0"),
        sa.Column("chunk_total",    sa.Integer,     nullable=False, server_default="1"),
        sa.Column("author",         sa.String(100), nullable=False, server_default=""),
        sa.Column("url",            sa.String(500), nullable=False, server_default=""),
        sa.Column("published_date", sa.String(10),  nullable=False, server_default=""),
        sa.Column("article_type",   sa.String(20),  nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["raw_articles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", name="uq_article_chunks_chunk_id"),
    )

    # Replace placeholder text column with native vector(1024) type
    op.execute("ALTER TABLE article_chunks ALTER COLUMN embedding TYPE vector(1024) USING NULL::vector(1024)")

    op.create_index("ix_article_chunks_source_id",      "article_chunks", ["source_id"])
    op.create_index("ix_article_chunks_article_id",     "article_chunks", ["article_id"])
    op.create_index("ix_article_chunks_published_date", "article_chunks", ["published_date"])

    # HNSW index for fast approximate cosine search
    op.execute(
        "CREATE INDEX ix_article_chunks_embedding_hnsw "
        "ON article_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("article_chunks")
