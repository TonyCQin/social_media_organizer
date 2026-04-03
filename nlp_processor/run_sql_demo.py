import argparse
import sqlite3
from pathlib import Path
from typing import List


def split_sql_statements(sql_text: str) -> List[str]:
    statements: List[str] = []
    buffer: List[str] = []

    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        buffer.append(line)

    cleaned_sql = "\n".join(buffer)
    for chunk in cleaned_sql.split(";"):
        statement = chunk.strip()
        if statement:
            statements.append(statement)
    return statements


def run_sql_file(db_path: Path, sql_file_path: Path, max_rows: int = 20) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")
    if not sql_file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")

    sql_text = sql_file_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        for index, statement in enumerate(statements, start=1):
            print(f"\n=== Query {index} ===")
            try:
                cursor.execute(statement)
                rows = cursor.fetchall()

                if not rows:
                    print("(no rows)")
                    continue

                columns = rows[0].keys()
                print(" | ".join(columns))
                print("-" * 80)
                for row in rows[:max_rows]:
                    print(" | ".join(str(row[col]) for col in columns))

                if len(rows) > max_rows:
                    print(f"... truncated {len(rows) - max_rows} additional row(s)")

            except sqlite3.Error as exc:
                print(f"ERROR: {exc}")
    finally:
        conn.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run report SQL demo queries against the project SQLite database.")
    parser.add_argument(
        "--db",
        default="nlp_processor/storage/social_media.db",
        help="Path to SQLite database file.",
    )
    parser.add_argument(
        "--sql",
        default="nlp_processor/examples/report_sql_demo.sql",
        help="Path to SQL file with demo queries.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=20,
        help="Maximum rows to print per query.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    run_sql_file(db_path=Path(args.db), sql_file_path=Path(args.sql), max_rows=args.max_rows)


if __name__ == "__main__":
    main()
