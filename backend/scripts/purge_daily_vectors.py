"""
One-time script: remove ChromaDB vectors for all daily-type sources.

Daily sources are for short-form trading news and go straight to the DB.
They should never have been vectorized. Run this once to clean up.

Usage (from backend/ directory):
    uv run python scripts/purge_daily_vectors.py
"""

import sys
from pathlib import Path

# Allow imports from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import SessionLocal, init_db
from db.models import RawArticle, Source
from vector_store.chroma_store import delete_collection


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
        vectorized_count = (
            db.query(RawArticle)
            .filter(RawArticle.source_id.in_(daily_ids), RawArticle.vectorized == True)  # noqa: E712
            .count()
        )

        if vectorized_count == 0:
            print("这些数据源没有已向量化的文章，无需清理。")
            return

        print(f"\n发现 {vectorized_count} 篇已向量化的 daily 文章，准备清理…")
        confirm = input("确认删除？[y/N] ").strip().lower()
        if confirm != "y":
            print("已取消。")
            return

        deleted_sources = 0
        for source in daily_sources:
            delete_collection(source.id)
            deleted_sources += 1
            print(f"  ✓ 已删除向量集合：{source.name}")

        db.query(RawArticle).filter(
            RawArticle.source_id.in_(daily_ids),
            RawArticle.vectorized == True,  # noqa: E712
        ).update({"vectorized": False}, synchronize_session=False)
        db.commit()

        print(f"\n完成：清理了 {deleted_sources} 个数据源的向量集合，重置了 {vectorized_count} 篇文章的状态。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
