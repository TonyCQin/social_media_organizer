import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _coerce_bool(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) else 0
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"true", "1", "yes", "y"}:
            return 1
        if low in {"false", "0", "no", "n"}:
            return 0
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_pipe_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return []


def _normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    owner = record.get("owner") if isinstance(record.get("owner"), dict) else {}
    location = record.get("location") if isinstance(record.get("location"), dict) else {}
    engagement = record.get("engagement") if isinstance(record.get("engagement"), dict) else {}
    media = record.get("media") if isinstance(record.get("media"), dict) else {}

    if not owner and any(k in record for k in ["owner_id", "owner_username", "owner_full_name", "owner_is_verified"]):
        owner = {
            "id": record.get("owner_id"),
            "username": record.get("owner_username"),
            "full_name": record.get("owner_full_name"),
            "is_verified": record.get("owner_is_verified"),
        }

    if not location and any(k in record for k in ["location_id", "location_name", "location_slug"]):
        location = {
            "id": record.get("location_id"),
            "name": record.get("location_name"),
            "slug": record.get("location_slug"),
        }

    if not engagement and any(k in record for k in ["likes", "comments", "video_views"]):
        engagement = {
            "likes": record.get("likes"),
            "comments": record.get("comments"),
            "video_views": record.get("video_views"),
        }

    if not media and any(
        k in record for k in ["display_url", "thumbnail_src", "video_url", "video_duration", "sidecar_items"]
    ):
        media = {
            "display_url": record.get("display_url"),
            "thumbnail_src": record.get("thumbnail_src"),
            "video_url": record.get("video_url"),
            "video_duration": record.get("video_duration"),
            "sidecar_items": record.get("sidecar_items"),
        }

    post_id = record.get("id") or record.get("post_id")
    if not post_id:
        raise ValueError("Record is missing required id/post_id")

    return {
        "post_id": str(post_id),
        "shortcode": record.get("shortcode"),
        "permalink": record.get("permalink"),
        "typename": record.get("typename"),
        "product_type": record.get("product_type"),
        "is_video": _coerce_bool(record.get("is_video")),
        "timestamp_utc": _coerce_int(record.get("timestamp_utc")),
        "datetime_utc": record.get("datetime_utc"),
        "caption": record.get("caption"),
        "caption_word_count": _coerce_int(record.get("caption_word_count")),
        "owner_id": owner.get("id"),
        "owner_username": owner.get("username"),
        "owner_full_name": owner.get("full_name"),
        "owner_is_verified": _coerce_bool(owner.get("is_verified")),
        "location_id": location.get("id"),
        "location_name": location.get("name"),
        "location_slug": location.get("slug"),
        "likes": _coerce_int(engagement.get("likes")),
        "comments": _coerce_int(engagement.get("comments")),
        "video_views": _coerce_int(engagement.get("video_views")),
        "display_url": media.get("display_url"),
        "thumbnail_src": media.get("thumbnail_src"),
        "video_url": media.get("video_url"),
        "video_duration": _coerce_float(media.get("video_duration")),
        "sidecar_items": _coerce_int(media.get("sidecar_items")),
        "text_for_nlp": record.get("text_for_nlp"),
        "source_file": record.get("source_file"),
        "hashtags": _split_pipe_list(record.get("hashtags")),
        "caption_mentions": _split_pipe_list(record.get("caption_mentions")),
        "tagged_usernames": _split_pipe_list(record.get("tagged_usernames")),
        "error": record.get("error"),
        "raw_json": json.dumps(record, ensure_ascii=False),
    }


def _iter_ndjson_records(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object JSON on line {line_number}")
            yield payload


def _iter_csv_records(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield dict(row)


def iter_input_records(path: Path, input_format: str) -> Iterable[Dict[str, Any]]:
    if input_format == "auto":
        lower = path.name.lower()
        if lower.endswith(".ndjson"):
            input_format = "ndjson"
        elif lower.endswith(".csv"):
            input_format = "csv"
        else:
            raise ValueError("Could not infer input format. Use --input-format ndjson or csv.")

    if input_format == "ndjson":
        yield from _iter_ndjson_records(path)
        return

    if input_format == "csv":
        yield from _iter_csv_records(path)
        return

    raise ValueError(f"Unsupported input format: {input_format}")


def apply_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    conn.executescript(sql)


def _upsert_record(conn: sqlite3.Connection, record: Dict[str, Any], parser_version: str) -> None:
    conn.execute(
        """
        INSERT INTO raw_instagram_posts(post_id, shortcode, source_file, raw_json, parser_version)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(post_id) DO UPDATE SET
            shortcode = excluded.shortcode,
            source_file = excluded.source_file,
            raw_json = excluded.raw_json,
            parser_version = excluded.parser_version,
            ingested_at = CURRENT_TIMESTAMP
        """,
        (
            record["post_id"],
            record["shortcode"],
            record["source_file"],
            record["raw_json"],
            parser_version,
        ),
    )

    conn.execute(
        """
        INSERT INTO normalized_posts(
            post_id, shortcode, permalink, typename, product_type, is_video,
            timestamp_utc, datetime_utc, caption, caption_word_count,
            owner_id, owner_username, owner_full_name, owner_is_verified,
            location_id, location_name, location_slug,
            likes, comments, video_views,
            display_url, thumbnail_src, video_url, video_duration, sidecar_items,
            text_for_nlp, source_file, parser_version, ingest_status, nlp_status, last_error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(post_id) DO UPDATE SET
            shortcode = excluded.shortcode,
            permalink = excluded.permalink,
            typename = excluded.typename,
            product_type = excluded.product_type,
            is_video = excluded.is_video,
            timestamp_utc = excluded.timestamp_utc,
            datetime_utc = excluded.datetime_utc,
            caption = excluded.caption,
            caption_word_count = excluded.caption_word_count,
            owner_id = excluded.owner_id,
            owner_username = excluded.owner_username,
            owner_full_name = excluded.owner_full_name,
            owner_is_verified = excluded.owner_is_verified,
            location_id = excluded.location_id,
            location_name = excluded.location_name,
            location_slug = excluded.location_slug,
            likes = excluded.likes,
            comments = excluded.comments,
            video_views = excluded.video_views,
            display_url = excluded.display_url,
            thumbnail_src = excluded.thumbnail_src,
            video_url = excluded.video_url,
            video_duration = excluded.video_duration,
            sidecar_items = excluded.sidecar_items,
            text_for_nlp = excluded.text_for_nlp,
            source_file = excluded.source_file,
            parser_version = excluded.parser_version,
            ingest_status = excluded.ingest_status,
            last_error = excluded.last_error,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            record["post_id"],
            record["shortcode"],
            record["permalink"],
            record["typename"],
            record["product_type"],
            record["is_video"],
            record["timestamp_utc"],
            record["datetime_utc"],
            record["caption"],
            record["caption_word_count"],
            record["owner_id"],
            record["owner_username"],
            record["owner_full_name"],
            record["owner_is_verified"],
            record["location_id"],
            record["location_name"],
            record["location_slug"],
            record["likes"],
            record["comments"],
            record["video_views"],
            record["display_url"],
            record["thumbnail_src"],
            record["video_url"],
            record["video_duration"],
            record["sidecar_items"],
            record["text_for_nlp"],
            record["source_file"],
            parser_version,
            "ingested",
            "pending",
            record["error"],
        ),
    )

    conn.execute("DELETE FROM post_hashtags WHERE post_id = ?", (record["post_id"],))
    conn.execute("DELETE FROM post_mentions WHERE post_id = ?", (record["post_id"],))
    conn.execute("DELETE FROM post_tagged_users WHERE post_id = ?", (record["post_id"],))

    conn.executemany(
        "INSERT OR IGNORE INTO post_hashtags(post_id, hashtag) VALUES (?, ?)",
        [(record["post_id"], tag) for tag in record["hashtags"]],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO post_mentions(post_id, mention) VALUES (?, ?)",
        [(record["post_id"], mention) for mention in record["caption_mentions"]],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO post_tagged_users(post_id, tagged_username) VALUES (?, ?)",
        [(record["post_id"], username) for username in record["tagged_usernames"]],
    )


def load_records_to_sqlite(
    input_path: Path,
    db_path: Path,
    schema_path: Path,
    input_format: str,
    parser_version: str,
    limit: Optional[int],
) -> Dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    processed = 0
    failed = 0

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        apply_schema(conn, schema_path)

        with conn:
            for raw in iter_input_records(input_path, input_format=input_format):
                if limit is not None and processed >= limit:
                    break

                try:
                    normalized = _normalize_record(raw)
                    _upsert_record(conn, normalized, parser_version=parser_version)
                except Exception:
                    failed += 1
                finally:
                    processed += 1
    finally:
        conn.close()

    return {
        "processed": processed,
        "failed": failed,
        "succeeded": processed - failed,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load parser output (NDJSON/CSV) into SQLite storage tables.")
    parser.add_argument("--input", required=True, help="Input file path (.ndjson or .csv).")
    parser.add_argument("--db", default="nlp_processor/storage/social_media.db", help="Output SQLite database path.")
    parser.add_argument(
        "--schema",
        default="nlp_processor/storage/schema.sql",
        help="Schema SQL file path used to initialize the database.",
    )
    parser.add_argument(
        "--input-format",
        choices=["auto", "ndjson", "csv"],
        default="auto",
        help="Input format. Defaults to auto infer from file extension.",
    )
    parser.add_argument("--parser-version", default="instagram_parser_v1", help="Parser version tag for lineage.")
    parser.add_argument("--limit", type=int, default=None, help="Optional record limit for test loads.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    input_path = Path(args.input)
    db_path = Path(args.db)
    schema_path = Path(args.schema)

    stats = load_records_to_sqlite(
        input_path=input_path,
        db_path=db_path,
        schema_path=schema_path,
        input_format=args.input_format,
        parser_version=args.parser_version,
        limit=args.limit,
    )

    print(
        f"Loaded {stats['processed']} records into {db_path}. "
        f"Succeeded: {stats['succeeded']}. Failed: {stats['failed']}."
    )


if __name__ == "__main__":
    main()
