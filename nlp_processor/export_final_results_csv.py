import argparse
import csv
import sqlite3
from pathlib import Path


def export_final_results(db_path: Path, full_csv: Path, readable_csv: Path) -> tuple[int, int, int]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT f.*, p.caption
            FROM final_post_classifications f
            LEFT JOIN normalized_posts p ON p.post_id = f.post_id
            ORDER BY f.datetime_utc DESC
            """
        ).fetchall()
        if not rows:
            raise SystemExit("No rows in final_post_classifications")

        full_csv.parent.mkdir(parents=True, exist_ok=True)
        with full_csv.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))

        readable_rows = conn.execute(
            """
            SELECT
                f.post_id,
                f.datetime_utc,
                f.permalink,
                p.caption,
                f.owner_username,
                f.location_name,
                f.final_model_version,
                f.category,
                f.meal_type,
                f.cuisines,
                f.content_type,
                f.confidence,
                f.needs_review,
                f.rationale
            FROM final_post_classifications AS f
            LEFT JOIN normalized_posts AS p ON p.post_id = f.post_id
            ORDER BY f.datetime_utc DESC
            """
        ).fetchall()

        readable_csv.parent.mkdir(parents=True, exist_ok=True)
        with readable_csv.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(readable_rows[0].keys()))
            writer.writeheader()
            for row in readable_rows:
                writer.writerow(dict(row))

        return len(rows), len(rows[0].keys()), len(readable_rows[0].keys())
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export final classification tables to CSV")
    parser.add_argument(
        "--db",
        default="nlp_processor/storage/social_media.db",
        help="SQLite database path",
    )
    parser.add_argument(
        "--full-csv",
        default="nlp_processor/examples/final_post_classifications.csv",
        help="Output path for the full export",
    )
    parser.add_argument(
        "--readable-csv",
        default="nlp_processor/examples/final_post_classifications_readable.csv",
        help="Output path for the readable export",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    full_csv = Path(args.full_csv)
    readable_csv = Path(args.readable_csv)
    row_count, full_columns, readable_columns = export_final_results(db_path, full_csv, readable_csv)

    print(f"full_csv={full_csv}")
    print(f"readable_csv={readable_csv}")
    print(f"rows={row_count}")
    print(f"full_columns={full_columns}")
    print(f"readable_columns={readable_columns}")


if __name__ == "__main__":
    main()
