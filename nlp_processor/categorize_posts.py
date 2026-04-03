import argparse
import csv
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


MEAL_RULES: Dict[str, Sequence[str]] = {
    "breakfast": ["breakfast", "bagel", "pancake", "waffle", "eggs", "omelet", "omelette"],
    "brunch": ["brunch", "mimosa", "benedict", "avocado toast"],
    "lunch": ["lunch", "sandwich", "lunch special", "midday"],
    "dinner": ["dinner", "date night", "supper", "tasting menu"],
    "dessert": ["dessert", "ice cream", "gelato", "cake", "cookie", "donut", "sweet tooth"],
    "drinks": [
        "cocktail",
        "cocktails",
        "alcohol",
        "liquor",
        "spirits",
        "booze",
        "wine",
        "beer",
        "brewery",
        "bar",
        "mocktail",
        "drink",
        "drinks",
        "happy hour",
        "margarita",
        "martini",
        "whiskey",
        "bourbon",
        "vodka",
        "tequila",
        "gin",
        "rum",
        "shot",
        "shots",
        "aperitif",
    ],
    "snack": ["snack", "quick bite", "street food", "small bites"],
}


CUISINE_RULES: Dict[str, Sequence[str]] = {
    "american": ["american", "burger", "hot dog", "fried chicken", "southern"],
    "mexican": ["mexican", "taco", "burrito", "quesadilla", "birria", "elote"],
    "italian": ["italian", "pasta", "pizza", "risotto", "gnocchi"],
    "japanese": ["japanese", "sushi", "ramen", "omakase", "izakaya", "udon"],
    "korean": ["korean", "kimchi", "kbbq", "bibimbap", "bulgogi", "tteokbokki"],
    "chinese": ["chinese", "dim sum", "dumpling", "hot pot", "szechuan"],
    "thai": ["thai", "pad thai", "tom yum", "green curry"],
    "indian": ["indian", "curry", "biryani", "naan", "masala"],
    "mediterranean": ["mediterranean", "falafel", "shawarma", "hummus", "gyro"],
    "seafood": ["seafood", "oyster", "lobster", "shrimp", "crab", "fish"],
    "bbq": ["bbq", "barbecue", "smoked", "brisket", "ribs"],
    "vegan": ["vegan", "plant-based", "plant based", "dairy free"],
    "bakery": ["bakery", "pastry", "croissant", "bread", "bakehouse"],
    "coffee_cafe": ["coffee", "cafe", "espresso", "latte", "matcha"],
}


EVENT_RULES: Sequence[str] = [
    "festival",
    "event",
    "market",
    "popup",
    "pop-up",
    "concert",
    "live music",
    "opening weekend",
    "grand opening",
    "ticket",
    "limited time",
    "seasonal",
]


ACTIVITY_RULES: Sequence[str] = [
    "museum",
    "experience",
    "arcade",
    "activity",
    "exhibit",
    "show",
    "walk",
    "park",
    "trail",
]


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _parse_pipe_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip().lower() for item in value.split("|") if item.strip()]


def _keyword_hits(text: str, keywords: Sequence[str]) -> List[str]:
    hits: List[str] = []
    for keyword in keywords:
        if keyword in text:
            hits.append(keyword)
    return hits


def classify_meal_type(text_blob: str) -> Tuple[str, float, Dict[str, List[str]]]:
    scores: Dict[str, int] = {}
    evidence: Dict[str, List[str]] = {}
    for label, keywords in MEAL_RULES.items():
        hits = _keyword_hits(text_blob, keywords)
        if hits:
            scores[label] = len(hits)
            evidence[label] = hits

    if not scores:
        return "unknown", 0.35, {}

    best_label = max(scores, key=scores.get)
    confidence = min(0.55 + 0.1 * scores[best_label], 0.95)
    return best_label, confidence, evidence


def classify_cuisines(text_blob: str) -> Tuple[List[str], Dict[str, List[str]]]:
    cuisines: List[str] = []
    evidence: Dict[str, List[str]] = {}

    for label, keywords in CUISINE_RULES.items():
        hits = _keyword_hits(text_blob, keywords)
        if hits:
            cuisines.append(label)
            evidence[label] = hits

    return cuisines, evidence


def classify_content_type(text_blob: str, has_location: bool) -> Tuple[str, float, Dict[str, List[str]]]:
    event_hits = _keyword_hits(text_blob, EVENT_RULES)
    activity_hits = _keyword_hits(text_blob, ACTIVITY_RULES)

    if event_hits:
        confidence = min(0.65 + 0.05 * len(event_hits), 0.95)
        return "event", confidence, {"event": event_hits}

    if activity_hits and not has_location:
        confidence = min(0.6 + 0.05 * len(activity_hits), 0.9)
        return "activity", confidence, {"activity": activity_hits}

    if has_location:
        return "food_spot", 0.7, {"food_spot": ["location_present"]}

    if activity_hits:
        return "activity", 0.58, {"activity": activity_hits}

    return "mixed", 0.45, {}


def _serialize_evidence(evidence: Dict[str, List[str]]) -> str:
    if not evidence:
        return ""
    parts: List[str] = []
    for label, hits in evidence.items():
        if hits:
            parts.append(f"{label}=>{','.join(hits)}")
    return " | ".join(parts)


def _build_decision_reason(
    top_category: str,
    content_type: str,
    meal_type: str,
    meal_evidence: Dict[str, List[str]],
    cuisine_evidence: Dict[str, List[str]],
    content_evidence: Dict[str, List[str]],
    has_location: bool,
    transcript: str,
) -> str:
    reasons: List[str] = []

    if top_category == "event" and "event" in content_evidence:
        reasons.append(f"event_keywords={','.join(content_evidence['event'])}")
    elif top_category == meal_type and meal_type in meal_evidence:
        reasons.append(f"meal_keywords={','.join(meal_evidence[meal_type])}")

    if cuisine_evidence:
        matched_cuisines = sorted(cuisine_evidence.keys())
        reasons.append(f"cuisine_matches={','.join(matched_cuisines)}")

    reasons.append(f"content_type={content_type}")
    reasons.append(f"location_present={has_location}")
    reasons.append(f"transcript_present={bool((transcript or '').strip())}")

    return " ; ".join(reasons)


def build_text_blob(caption: str, transcript: str, hashtags: List[str], mentions: List[str]) -> str:
    parts = [caption or "", transcript or "", " ".join(hashtags), " ".join(mentions)]
    return "\n".join(p for p in parts if p).lower()


def fetch_posts(conn: sqlite3.Connection, limit: Optional[int], only_pending: bool) -> List[sqlite3.Row]:
    query = """
        SELECT
            p.post_id,
            p.shortcode,
            p.datetime_utc,
            p.caption,
            p.location_name,
            p.location_slug,
            p.likes,
            p.comments,
            p.video_views,
            p.permalink,
            p.nlp_status,
            t.transcript,
            (
                SELECT GROUP_CONCAT(hashtag, '|')
                FROM post_hashtags h
                WHERE h.post_id = p.post_id
            ) AS hashtags,
            (
                SELECT GROUP_CONCAT(mention, '|')
                FROM post_mentions m
                WHERE m.post_id = p.post_id
            ) AS mentions
        FROM normalized_posts p
        LEFT JOIN video_transcripts t ON t.post_id = p.post_id
    """

    conditions: List[str] = []
    params: List[Any] = []

    if only_pending:
        conditions.append("p.nlp_status IN ('pending', 'transcribed', 'ingested')")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY COALESCE(p.video_views, 0) DESC, COALESCE(p.likes, 0) DESC"

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    return list(cur.fetchall())


def upsert_enrichment(conn: sqlite3.Connection, post_id: str, category: str, confidence: float, place_name: Optional[str], entities: Dict[str, Any], model_version: str) -> None:
    conn.execute(
        """
        INSERT INTO nlp_enrichments (post_id, model_version, category, confidence, place_name, entities_json, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(post_id, model_version) DO UPDATE SET
            category = excluded.category,
            confidence = excluded.confidence,
            place_name = excluded.place_name,
            entities_json = excluded.entities_json,
            processed_at = excluded.processed_at
        """,
        (
            post_id,
            model_version,
            category,
            confidence,
            place_name,
            json.dumps(entities, ensure_ascii=False),
            datetime.now(UTC).isoformat(),
        ),
    )

    conn.execute(
        "UPDATE normalized_posts SET nlp_status = 'categorized', updated_at = CURRENT_TIMESTAMP WHERE post_id = ?",
        (post_id,),
    )


def categorize_posts(conn: sqlite3.Connection, limit: Optional[int], only_pending: bool, model_version: str) -> List[Dict[str, Any]]:
    rows = fetch_posts(conn, limit=limit, only_pending=only_pending)
    output: List[Dict[str, Any]] = []

    for row in rows:
        caption = row["caption"] or ""
        transcript = row["transcript"] or ""
        hashtags = _parse_pipe_list(row["hashtags"])
        mentions = _parse_pipe_list(row["mentions"])
        has_location = bool((row["location_name"] or "").strip())

        text_blob = build_text_blob(caption, transcript, hashtags, mentions)

        meal_type, meal_confidence, meal_evidence = classify_meal_type(text_blob)
        cuisines, cuisine_evidence = classify_cuisines(text_blob)
        content_type, content_confidence, content_evidence = classify_content_type(text_blob, has_location=has_location)

        top_category = content_type if content_type == "event" else meal_type
        confidence = round(max(meal_confidence, content_confidence), 3)

        place_name = row["location_name"] or None
        entities = {
            "meal_type": meal_type,
            "cuisines": cuisines,
            "content_type": content_type,
            "location": {
                "name": row["location_name"],
                "slug": row["location_slug"],
            },
            "signals": {
                "meal_evidence": meal_evidence,
                "cuisine_evidence": cuisine_evidence,
                "content_evidence": content_evidence,
            },
            "metadata": {
                "hashtags": hashtags,
                "mentions": mentions,
                "likes": row["likes"],
                "comments": row["comments"],
                "video_views": row["video_views"],
            },
        }

        explanation = _build_decision_reason(
            top_category=top_category,
            content_type=content_type,
            meal_type=meal_type,
            meal_evidence=meal_evidence,
            cuisine_evidence=cuisine_evidence,
            content_evidence=content_evidence,
            has_location=has_location,
            transcript=transcript,
        )

        upsert_enrichment(
            conn=conn,
            post_id=row["post_id"],
            category=top_category,
            confidence=confidence,
            place_name=place_name,
            entities=entities,
            model_version=model_version,
        )

        output.append(
            {
                "post_id": row["post_id"],
                "shortcode": row["shortcode"],
                "datetime_utc": row["datetime_utc"],
                "permalink": row["permalink"],
                "category": top_category,
                "content_type": content_type,
                "meal_type": meal_type,
                "cuisines": "|".join(cuisines),
                "location_name": row["location_name"],
                "confidence": confidence,
                "hashtags": "|".join(hashtags),
                "mentions": "|".join(mentions),
                "caption_present": bool(caption.strip()),
                "caption_word_count": len(caption.split()) if caption else 0,
                "transcript_present": bool(transcript.strip()),
                "transcript_word_count": len(transcript.split()) if transcript else 0,
                "has_location": has_location,
                "meal_evidence": _serialize_evidence(meal_evidence),
                "cuisine_evidence": _serialize_evidence(cuisine_evidence),
                "content_evidence": _serialize_evidence(content_evidence),
                "decision_reason": explanation,
            }
        )

    conn.commit()
    return output


def write_report(rows: List[Dict[str, Any]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "post_id",
        "shortcode",
        "datetime_utc",
        "permalink",
        "category",
        "content_type",
        "meal_type",
        "cuisines",
        "location_name",
        "confidence",
        "hashtags",
        "mentions",
        "caption_present",
        "caption_word_count",
        "transcript_present",
        "transcript_word_count",
        "has_location",
        "meal_evidence",
        "cuisine_evidence",
        "content_evidence",
        "decision_reason",
    ]

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Categorize posts using metadata + transcript rules.")
    parser.add_argument("--db", default="nlp_processor/storage/social_media.db", help="SQLite database path.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for number of posts to categorize.")
    parser.add_argument("--all", action="store_true", help="Process all posts instead of only pending/transcribed records.")
    parser.add_argument(
        "--model-version",
        default="rules-food-events-v1",
        help="Model version tag used in nlp_enrichments.",
    )
    parser.add_argument(
        "--output-csv",
        default="nlp_processor/examples/post_categories_report.csv",
        help="Output CSV path for categorization report.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    db_path = Path(args.db)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        rows = categorize_posts(
            conn=conn,
            limit=args.limit,
            only_pending=not args.all,
            model_version=args.model_version,
        )
    finally:
        conn.close()

    output_csv = Path(args.output_csv)
    write_report(rows, output_csv)

    print(f"Categorized {len(rows)} posts.")
    print(f"Report: {output_csv}")
    if rows:
        sample = rows[0]
        print(
            "Sample:",
            f"post_id={sample['post_id']}",
            f"category={sample['category']}",
            f"meal_type={sample['meal_type']}",
            f"cuisines={sample['cuisines']}",
            f"confidence={sample['confidence']}",
        )


if __name__ == "__main__":
    main()
