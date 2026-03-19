import argparse
import sqlite3
from pathlib import Path


def _scalar(conn: sqlite3.Connection, query: str) -> int:
    row = conn.execute(query).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def print_summary(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        posts = _scalar(conn, "SELECT COUNT(*) FROM normalized_posts")
        hashtags = _scalar(conn, "SELECT COUNT(*) FROM post_hashtags")
        mentions = _scalar(conn, "SELECT COUNT(*) FROM post_mentions")
        tagged = _scalar(conn, "SELECT COUNT(*) FROM post_tagged_users")
        pending_nlp = _scalar(conn, "SELECT COUNT(*) FROM normalized_posts WHERE nlp_status = 'pending'")
        with_errors = _scalar(
            conn,
            "SELECT COUNT(*) FROM normalized_posts WHERE last_error IS NOT NULL AND TRIM(last_error) <> ''",
        )

        print(f"DB: {db_path}")
        print(f"Posts: {posts}")
        print(f"Hashtag rows: {hashtags}")
        print(f"Mention rows: {mentions}")
        print(f"Tagged user rows: {tagged}")
        print(f"Pending NLP rows: {pending_nlp}")
        print(f"Rows with ingest errors: {with_errors}")

        print("\nTop locations:")
        for location_name, count in conn.execute(
            """
            SELECT COALESCE(location_name, '[none]') AS location_name, COUNT(*) AS cnt
            FROM normalized_posts
            GROUP BY COALESCE(location_name, '[none]')
            ORDER BY cnt DESC, location_name ASC
            LIMIT 10
            """
        ):
            print(f"- {location_name}: {count}")
    finally:
        conn.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show quick summary stats for the SQLite ingestion database.")
    parser.add_argument("--db", default="nlp_processor/storage/social_media.db", help="SQLite database path.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    print_summary(Path(args.db))


if __name__ == "__main__":
    main()
