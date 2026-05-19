"""
One-time script: remove pgvector chunks for all daily-type sources.

Daily sources are for short-form trading news and go straight to the DB.
They should never have been vectorized. Run this once to clean up.

Usage (from backend/ directory):
    uv run python scripts/purge_daily_vectors.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import SessionLocal, init_db
from db.models import ArticleChunk, RawArticle, Source


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        daily_sources = db.query(Source).filter(Source.content_type == "daily").all()
        if not daily_sources:
            print("没有找到 daily 类型的数据源，无需清理。")
            return

        print(f"找到 {len(daily_sources)} 个 daily 数据源：")
        for s in daily_sources:
            print(f"  - {s.name} ({s.id})")

        daily_ids = [s.id for s in daily_sources]
        chunk_count = (
            db.query(ArticleChunk)
            .filter(ArticleChunk.source_id.in_(daily_ids))
            .count()
        )

        if chunk_count == 0:
            print("这些数据源没有向量块，无需清理。")
            return

        print(f"\n发现 {chunk_count} 个向量块，准备清理…")
        confirm = input("确认删除？[y/N] ").strip().lower()
        if confirm != "y":
            print("已取消。")
            return

        deleted = (
            db.query(ArticleChunk)
            .filter(ArticleChunk.source_id.in_(daily_ids))
            .delete(synchronize_session=False)
        )
        db.query(RawArticle).filter(
            RawArticle.source_id.in_(daily_ids),
            RawArticle.vectorized == True,  # noqa: E712
        ).update({"vectorized": False}, synchronize_session=False)
        db.commit()

        print(f"\n完成：删除了 {deleted} 个向量块，并重置了对应文章的 vectorized 标志。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
