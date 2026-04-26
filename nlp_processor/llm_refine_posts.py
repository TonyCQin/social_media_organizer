import argparse
import csv
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request


MEAL_TYPES = [
    "breakfast",
    "brunch",
    "lunch",
    "dinner",
    "dessert",
    "drinks",
    "all_day",
    "snack",
    "unknown",
]

CUISINE_TYPES = [
    "american",
    "mexican",
    "italian",
    "japanese",
    "korean",
    "chinese",
    "thai",
    "indian",
    "mediterranean",
    "seafood",
    "bbq",
    "vegan",
    "bakery",
    "coffee_cafe",
]

CONTENT_TYPES = ["food_spot", "event", "activity", "mixed"]

CUISINE_ALIASES = {
    "korea": "korean",
    "korean bbq": "korean",
    "barbecue": "bbq",
    "cafe": "coffee_cafe",
    "coffee": "coffee_cafe",
}


def _safe_entities(row_entities_json: Optional[str]) -> Dict[str, Any]:
    try:
        return json.loads(row_entities_json or "{}")
    except json.JSONDecodeError:
        return {}


def _extract_list_field(entities_json: Optional[str], key: str) -> str:
    entities = _safe_entities(entities_json)
    value = entities.get(key, [])
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    if isinstance(value, str):
        return value
    return ""


def _extract_scalar_field(entities_json: Optional[str], key: str, default: str = "") -> str:
    entities = _safe_entities(entities_json)
    value = entities.get(key, default)
    return str(value) if value is not None else default


def _extract_nested_field(entities_json: Optional[str], path: List[str], default: Any = None) -> Any:
    entities = _safe_entities(entities_json)
    current: Any = entities
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def fetch_source_enrichments(
    conn: sqlite3.Connection, source_model_version: str, limit: Optional[int] = None
) -> List[sqlite3.Row]:
    query = """
        SELECT
            e.post_id,
            e.category,
            e.confidence,
            e.entities_json,
            p.permalink,
            p.caption,
            p.location_name,
            (
                SELECT GROUP_CONCAT(hashtag, '|')
                FROM post_hashtags h
                WHERE h.post_id = p.post_id
            ) AS hashtags,
            (
                SELECT GROUP_CONCAT(mention, '|')
                FROM post_mentions m
                WHERE m.post_id = p.post_id
            ) AS mentions,
            (
                SELECT transcript FROM video_transcripts vt
                WHERE vt.post_id = p.post_id
                LIMIT 1
            ) AS transcript
        FROM nlp_enrichments e
        JOIN normalized_posts p ON e.post_id = p.post_id
        WHERE e.model_version = ?
        ORDER BY p.datetime_utc DESC
    """
    params: List[Any] = [source_model_version]
    if limit:
        query += "\nLIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    return cursor.fetchall()


def _normalize_meal(value: str) -> str:
    label = (value or "").strip().lower()
    return label if label in MEAL_TYPES else "unknown"


def _normalize_content(value: str) -> str:
    label = (value or "").strip().lower()
    return label if label in CONTENT_TYPES else "mixed"


def _normalize_cuisines(values: Any) -> List[str]:
    cuisines: List[str] = []
    if isinstance(values, str):
        raw = [part.strip().lower() for part in values.replace(";", "|").replace(",", "|").split("|")]
    elif isinstance(values, list):
        raw = [str(v).strip().lower() for v in values]
    else:
        raw = []

    for item in raw:
        if not item or item == "unknown":
            continue
        item = CUISINE_ALIASES.get(item, item)
        if item in CUISINE_TYPES and item not in cuisines:
            cuisines.append(item)
    return cuisines


def _resolve_category(meal_type: str, content_type: str, cuisines: List[str]) -> str:
    has_food_signal = meal_type != "unknown" or bool(cuisines)
    if content_type == "event":
        return "event"
    if content_type == "activity" and not has_food_signal:
        return "activity"
    return meal_type if meal_type != "unknown" else "unknown"


def _strip_code_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        first_newline = cleaned.find("\n")
        if first_newline >= 0:
            cleaned = cleaned[first_newline + 1 :]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_prompt_payload(row: sqlite3.Row, baseline_entities: Dict[str, Any]) -> Dict[str, Any]:
    hashtags = [item for item in (row["hashtags"] or "").split("|") if item]
    mentions = [item for item in (row["mentions"] or "").split("|") if item]

    return {
        "post": {
            "permalink": row["permalink"],
            "caption": row["caption"] or "",
            "location_name": row["location_name"],
            "hashtags": hashtags,
            "mentions": mentions,
            "transcript": row["transcript"] or "",
        },
        "baseline": {
            "category": row["category"],
            "confidence": float(row["confidence"] or 0.0),
            "meal_type": baseline_entities.get("meal_type", "unknown"),
            "cuisines": baseline_entities.get("cuisines", []),
            "content_type": baseline_entities.get("content_type", "mixed"),
        },
        "taxonomy": {
            "meal_types": MEAL_TYPES,
            "cuisine_types": CUISINE_TYPES,
            "content_types": CONTENT_TYPES,
        },
    }


def call_llm_for_labels(
    api_key: str,
    model: str,
    base_url: str,
    payload: Dict[str, Any],
    timeout_seconds: int,
) -> Dict[str, Any]:
    endpoint = base_url.rstrip("/") + "/chat/completions"

    system_prompt = (
        "You classify social-media food/event posts. Use only provided taxonomy values. "
        "Return strict JSON with keys: meal_type, cuisines, content_type, confidence, needs_review, rationale. "
        "confidence must be 0.0-1.0. cuisines must be an array."
    )
    user_prompt = json.dumps(payload, ensure_ascii=False)

    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    req = request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with request.urlopen(req, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
        parsed = json.loads(raw)

    content = parsed["choices"][0]["message"]["content"]
    content = _strip_code_fences(content)
    return json.loads(content)


def refine_posts_with_llm(
    conn: sqlite3.Connection,
    source_model_version: str,
    output_model_version: str,
    llm_model: str,
    llm_base_url: str,
    api_key: Optional[str],
    limit: Optional[int],
    dry_run: bool,
    sleep_seconds: float,
    timeout_seconds: int,
) -> int:
    rows = fetch_source_enrichments(conn, source_model_version=source_model_version, limit=limit)
    total = len(rows)
    if not rows:
        print(f"No source enrichments found for model_version='{source_model_version}'.")
        return 0

    if not dry_run and not api_key:
        raise ValueError("Missing API key. Set OPENAI_API_KEY or pass --api-key.")

    print(f"LLM refining {total} posts from '{source_model_version}' -> '{output_model_version}'...")

    cursor = conn.cursor()
    processed = 0

    for idx, row in enumerate(rows, 1):
        baseline_entities = _safe_entities(row["entities_json"])
        baseline_meal = _normalize_meal(str(baseline_entities.get("meal_type", "unknown")))
        baseline_cuisines = _normalize_cuisines(baseline_entities.get("cuisines", []))
        baseline_content = _normalize_content(str(baseline_entities.get("content_type", "mixed")))
        baseline_confidence = float(row["confidence"] or 0.0)

        if dry_run:
            llm_result = {
                "meal_type": baseline_meal,
                "cuisines": baseline_cuisines,
                "content_type": baseline_content,
                "confidence": baseline_confidence,
                "needs_review": False,
                "rationale": "dry_run_keep_source",
            }
        else:
            prompt_payload = _build_prompt_payload(row, baseline_entities)
            try:
                llm_result = call_llm_for_labels(
                    api_key=api_key or "",
                    model=llm_model,
                    base_url=llm_base_url,
                    payload=prompt_payload,
                    timeout_seconds=timeout_seconds,
                )
            except (error.HTTPError, error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
                llm_result = {
                    "meal_type": baseline_meal,
                    "cuisines": baseline_cuisines,
                    "content_type": baseline_content,
                    "confidence": baseline_confidence,
                    "needs_review": True,
                    "rationale": f"llm_error_fallback:{type(exc).__name__}",
                }

        meal_type = _normalize_meal(str(llm_result.get("meal_type", baseline_meal)))
        cuisines = _normalize_cuisines(llm_result.get("cuisines", baseline_cuisines))
        content_type = _normalize_content(str(llm_result.get("content_type", baseline_content)))
        confidence = llm_result.get("confidence", baseline_confidence)
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = baseline_confidence
        confidence_value = min(max(confidence_value, 0.0), 1.0)

        category = _resolve_category(meal_type=meal_type, content_type=content_type, cuisines=cuisines)

        llm_entities = {
            "meal_type": meal_type,
            "cuisines": cuisines,
            "content_type": content_type,
            "location": {"name": row["location_name"], "slug": None},
            "signals": {
                "source_model_version": source_model_version,
                "baseline_meal_type": baseline_meal,
                "baseline_cuisines": baseline_cuisines,
                "baseline_content_type": baseline_content,
                "baseline_confidence": baseline_confidence,
            },
            "metadata": {
                "hashtags": [item for item in (row["hashtags"] or "").split("|") if item],
                "mentions": [item for item in (row["mentions"] or "").split("|") if item],
                "llm_model": llm_model,
                "llm_base_url": llm_base_url,
                "refined_from": source_model_version,
            },
            "refinement": {
                "llm_raw": llm_result,
                "needs_review": bool(llm_result.get("needs_review", False)),
                "rationale": str(llm_result.get("rationale", "")),
            },
        }

        cursor.execute(
            """
            INSERT INTO nlp_enrichments (
                post_id, model_version, category, confidence, place_name, entities_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (post_id, model_version) DO UPDATE SET
                category = excluded.category,
                confidence = excluded.confidence,
                place_name = excluded.place_name,
                entities_json = excluded.entities_json
            """,
            (
                row["post_id"],
                output_model_version,
                category,
                round(confidence_value, 3),
                row["location_name"],
                json.dumps(llm_entities, ensure_ascii=False),
            ),
        )

        processed += 1
        if idx % 20 == 0:
            conn.commit()
            print(f"  [{idx}/{total}] LLM refined {idx} posts...")

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    conn.commit()
    print(f"LLM refined {processed} posts. Stored with model_version='{output_model_version}'.")
    return processed


def export_llm_refinement_report(
    conn: sqlite3.Connection,
    source_model_version: str,
    output_model_version: str,
    output_csv: Path,
) -> None:
    query = """
        SELECT
            b.post_id,
            p.permalink,
            b.category AS baseline_category,
            b.confidence AS baseline_confidence,
            l.category AS refined_category,
            l.confidence AS refined_confidence,
            CASE
                WHEN b.category != l.category THEN 'CHANGED'
                WHEN ABS(b.confidence - l.confidence) > 0.01 THEN 'CONFIDENCE_UPDATED'
                ELSE 'NO_CHANGE'
            END AS change_type,
            ROUND(l.confidence - b.confidence, 3) AS confidence_delta,
            b.entities_json AS baseline_entities,
            l.entities_json AS refined_entities
        FROM nlp_enrichments b
        JOIN nlp_enrichments l
            ON b.post_id = l.post_id
        JOIN normalized_posts p
            ON p.post_id = b.post_id
        WHERE b.model_version = ?
          AND l.model_version = ?
        ORDER BY change_type, confidence_delta DESC
    """

    rows = conn.execute(query, (source_model_version, output_model_version)).fetchall()
    if not rows:
        print("No LLM refinements to report.")
        return

    export_rows: List[Dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row)
        row_dict["baseline_meal_type"] = _extract_scalar_field(row_dict.get("baseline_entities"), "meal_type")
        row_dict["refined_meal_type"] = _extract_scalar_field(row_dict.get("refined_entities"), "meal_type")
        row_dict["baseline_content_type"] = _extract_scalar_field(row_dict.get("baseline_entities"), "content_type")
        row_dict["refined_content_type"] = _extract_scalar_field(row_dict.get("refined_entities"), "content_type")
        row_dict["baseline_cuisines"] = _extract_list_field(row_dict.get("baseline_entities"), "cuisines")
        row_dict["refined_cuisines"] = _extract_list_field(row_dict.get("refined_entities"), "cuisines")
        row_dict["needs_review"] = bool(
            _extract_nested_field(row_dict.get("refined_entities"), ["refinement", "needs_review"], False)
        )
        row_dict["category_adjustment_reason"] = _extract_nested_field(
            row_dict.get("refined_entities"), ["refinement", "rationale"], ""
        )
        export_rows.append(row_dict)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(export_rows[0].keys()))
        writer.writeheader()
        for row in export_rows:
            writer.writerow(row)

    print(f"LLM refinement report: {output_csv}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LLM refinement layer for contextual post labeling")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("nlp_processor/storage/social_media.db"),
        help="SQLite database path",
    )
    parser.add_argument(
        "--source-model-version",
        default="nlp-refined-v1",
        help="Input model_version from nlp_enrichments",
    )
    parser.add_argument(
        "--output-model-version",
        default="llm-refined-v1",
        help="Output model_version for LLM-refined rows",
    )
    parser.add_argument(
        "--llm-model",
        default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        help="Model name for chat/completions",
    )
    parser.add_argument(
        "--llm-base-url",
        default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="OpenAI-compatible base URL (without /chat/completions)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="API key (defaults to OPENAI_API_KEY)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional limit")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Delay between calls")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="HTTP timeout")
    parser.add_argument("--dry-run", action="store_true", help="Do not call LLM; copy baseline labels")
    parser.add_argument("--output-csv", type=Path, help="Optional comparison CSV export path")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.db.exists():
        raise FileNotFoundError(f"Database not found: {args.db}")

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row

    try:
        refine_posts_with_llm(
            conn=conn,
            source_model_version=args.source_model_version,
            output_model_version=args.output_model_version,
            llm_model=args.llm_model,
            llm_base_url=args.llm_base_url,
            api_key=args.api_key,
            limit=args.limit,
            dry_run=args.dry_run,
            sleep_seconds=args.sleep_seconds,
            timeout_seconds=args.timeout_seconds,
        )
        if args.output_csv:
            export_llm_refinement_report(
                conn=conn,
                source_model_version=args.source_model_version,
                output_model_version=args.output_model_version,
                output_csv=args.output_csv,
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
