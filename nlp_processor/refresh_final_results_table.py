import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_MODEL_PRIORITY = [
    "llm-refined-v1",
    "nlp-refined-v1",
    "rules-food-events-v1",
]


def _safe_entities(entities_json: Optional[str]) -> Dict[str, Any]:
    try:
        return json.loads(entities_json or "{}")
    except json.JSONDecodeError:
        return {}


def _extract_cuisines_pipe(entities: Dict[str, Any]) -> str:
    cuisines = entities.get("cuisines", [])
    if isinstance(cuisines, list):
        return "|".join(str(item) for item in cuisines)
    if isinstance(cuisines, str):
        return cuisines
    return ""


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS final_post_classifications (
            post_id TEXT PRIMARY KEY,
            permalink TEXT,
            datetime_utc TEXT,
            owner_username TEXT,
            location_name TEXT,
            final_model_version TEXT,
            category TEXT,
            confidence REAL,
            meal_type TEXT,
            cuisines TEXT,
            content_type TEXT,
            needs_review INTEGER NOT NULL DEFAULT 0,
            rationale TEXT,
            entities_json TEXT,
            selected_processed_at TEXT,
            refreshed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES normalized_posts(post_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_final_post_classifications_model ON final_post_classifications(final_model_version)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_final_post_classifications_category ON final_post_classifications(category)"
    )


def _pick_best_enrichment(
    enrichments: List[sqlite3.Row],
    model_priority: List[str],
) -> Optional[sqlite3.Row]:
    if not enrichments:
        return None

    priority = {model: idx for idx, model in enumerate(model_priority)}

    def sort_key(row: sqlite3.Row) -> Any:
        model = row["model_version"]
        model_rank = priority.get(model, len(model_priority) + 100)
        processed_at = row["processed_at"] or ""
        enrich_id = row["id"] or 0
        return (model_rank, processed_at, enrich_id)

    return sorted(enrichments, key=sort_key, reverse=False)[0]


def refresh_final_table(conn: sqlite3.Connection, model_priority: List[str]) -> int:
    ensure_table(conn)

    posts = conn.execute(
        """
        SELECT
            post_id,
            permalink,
            datetime_utc,
            owner_username,
            location_name
        FROM normalized_posts
        ORDER BY datetime_utc DESC
        """
    ).fetchall()

    placeholders = ",".join("?" for _ in model_priority)

    upsert_count = 0
    for post in posts:
        enrichments = conn.execute(
            f"""
            SELECT
                id,
                post_id,
                model_version,
                category,
                confidence,
                entities_json,
                processed_at
            FROM nlp_enrichments
            WHERE post_id = ?
              AND model_version IN ({placeholders})
            """,
            [post["post_id"], *model_priority],
        ).fetchall()

        chosen = _pick_best_enrichment(enrichments, model_priority)

        if chosen:
            entities = _safe_entities(chosen["entities_json"])
            meal_type = str(entities.get("meal_type", "unknown") or "unknown")
            cuisines = _extract_cuisines_pipe(entities)
            content_type = str(entities.get("content_type", "mixed") or "mixed")
            needs_review = int(
                bool(
                    entities.get("refinement", {}).get("needs_review", False)
                    if isinstance(entities.get("refinement"), dict)
                    else False
                )
            )
            rationale = ""
            refinement = entities.get("refinement", {})
            if isinstance(refinement, dict):
                rationale = str(
                    refinement.get("rationale", "")
                    or refinement.get("category_adjustment_reason", "")
                )

            conn.execute(
                """
                INSERT INTO final_post_classifications (
                    post_id,
                    permalink,
                    datetime_utc,
                    owner_username,
                    location_name,
                    final_model_version,
                    category,
                    confidence,
                    meal_type,
                    cuisines,
                    content_type,
                    needs_review,
                    rationale,
                    entities_json,
                    selected_processed_at,
                    refreshed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(post_id) DO UPDATE SET
                    permalink = excluded.permalink,
                    datetime_utc = excluded.datetime_utc,
                    owner_username = excluded.owner_username,
                    location_name = excluded.location_name,
                    final_model_version = excluded.final_model_version,
                    category = excluded.category,
                    confidence = excluded.confidence,
                    meal_type = excluded.meal_type,
                    cuisines = excluded.cuisines,
                    content_type = excluded.content_type,
                    needs_review = excluded.needs_review,
                    rationale = excluded.rationale,
                    entities_json = excluded.entities_json,
                    selected_processed_at = excluded.selected_processed_at,
                    refreshed_at = CURRENT_TIMESTAMP
                """,
                (
                    post["post_id"],
                    post["permalink"],
                    post["datetime_utc"],
                    post["owner_username"],
                    post["location_name"],
                    chosen["model_version"],
                    chosen["category"],
                    float(chosen["confidence"] or 0.0),
                    meal_type,
                    cuisines,
                    content_type,
                    needs_review,
                    rationale,
                    chosen["entities_json"],
                    chosen["processed_at"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO final_post_classifications (
                    post_id,
                    permalink,
                    datetime_utc,
                    owner_username,
                    location_name,
                    final_model_version,
                    category,
                    confidence,
                    meal_type,
                    cuisines,
                    content_type,
                    needs_review,
                    rationale,
                    entities_json,
                    selected_processed_at,
                    refreshed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(post_id) DO UPDATE SET
                    permalink = excluded.permalink,
                    datetime_utc = excluded.datetime_utc,
                    owner_username = excluded.owner_username,
                    location_name = excluded.location_name,
                    final_model_version = excluded.final_model_version,
                    category = excluded.category,
                    confidence = excluded.confidence,
                    meal_type = excluded.meal_type,
                    cuisines = excluded.cuisines,
                    content_type = excluded.content_type,
                    needs_review = excluded.needs_review,
                    rationale = excluded.rationale,
                    entities_json = excluded.entities_json,
                    selected_processed_at = excluded.selected_processed_at,
                    refreshed_at = CURRENT_TIMESTAMP
                """,
                (
                    post["post_id"],
                    post["permalink"],
                    post["datetime_utc"],
                    post["owner_username"],
                    post["location_name"],
                    "none",
                    "unknown",
                    0.0,
                    "unknown",
                    "",
                    "mixed",
                    1,
                    "no_enrichment_found",
                    "{}",
                    None,
                ),
            )

        upsert_count += 1

    conn.commit()
    return upsert_count


def print_summary(conn: sqlite3.Connection) -> None:
    total = conn.execute("SELECT COUNT(*) FROM final_post_classifications").fetchone()[0]
    print(f"Final results rows: {total}")

    print("Model usage:")
    for model_version, count in conn.execute(
        """
        SELECT final_model_version, COUNT(*)
        FROM final_post_classifications
        GROUP BY final_model_version
        ORDER BY COUNT(*) DESC
        """
    ):
        print(f"  - {model_version}: {count}")

    print("\nRecent sample:")
    for row in conn.execute(
        """
        SELECT post_id, final_model_version, category, meal_type, cuisines, content_type, confidence
        FROM final_post_classifications
        ORDER BY datetime_utc DESC
        LIMIT 5
        """
    ):
        print(
            f"  - post_id={row[0]} model={row[1]} category={row[2]} meal={row[3]} cuisines={row[4]} content={row[5]} conf={row[6]}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create/refresh canonical final post classification table")
    parser.add_argument(
        "--db",
        default="nlp_processor/storage/social_media.db",
        help="SQLite database path",
    )
    parser.add_argument(
        "--model-priority",
        default=",".join(DEFAULT_MODEL_PRIORITY),
        help="Comma-separated model_version priority (highest first)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    model_priority = [part.strip() for part in args.model_priority.split(",") if part.strip()]
    if not model_priority:
        raise ValueError("--model-priority must include at least one model version")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        refreshed = refresh_final_table(conn, model_priority=model_priority)
        print(f"Refreshed final_post_classifications for {refreshed} posts.")
        print_summary(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
