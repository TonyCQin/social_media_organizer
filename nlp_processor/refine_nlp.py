"""
NLP refinement layer: Use semantic embeddings to validate and refine baseline classifications.

Reads baseline classifications from nlp_enrichments (rules-food-events-v1), embeds post
content, and compares against reference embeddings for each category. Refines labels/
confidence scores and stores in nlp_enrichments with model_version='nlp-refined-v1'.

All posts are checked, regardless of baseline confidence.
"""

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from sentence_transformers import SentenceTransformer, util
except ImportError as exc:
    raise ImportError(
        "sentence-transformers not installed. Run: pip install sentence-transformers"
    ) from exc


MEAL_TYPE_REFERENCES = {
    "breakfast": "breakfast eggs pancakes waffles morning meal",
    "brunch": "brunch late morning meal mimosa eggs benedict",
    "lunch": "lunch midday meal sandwich salad",
    "dinner": "dinner evening meal date night supper entree",
    "dessert": "dessert sweet cake ice cream candy chocolate",
    "drinks": "drinks cocktails beer wine bar happy hour alcohol liquor spirits",
    "all_day": "all day all-day menu breakfast to dinner anytime dining",
    "snack": "snack quick bite appetizer street food",
    "unknown": "food meal eating",
}

CUISINE_TYPE_REFERENCES = {
    "american": "american cuisine american diner comfort food southern food",
    "mexican": "mexican taco burrito quesadilla salsa",
    "italian": "italian pasta pizza risotto gnocchi",
    "japanese": "japanese sushi ramen omakase izakaya udon",
    "korean": "korean kimchi kbbq bibimbap bulgogi tteokbokki",
    "chinese": "chinese dim sum dumpling hot pot szechuan",
    "thai": "thai pad thai tom yum curry green curry",
    "indian": "indian curry biryani naan masala",
    "mediterranean": "mediterranean falafel shawarma hummus gyro",
    "seafood": "seafood oyster lobster shrimp crab fish",
    "bbq": "bbq barbecue smoked brisket ribs",
    "vegan": "vegan plant-based dairy free vegetarian",
    "bakery": "bakery pastry croissant bread donut",
    "coffee_cafe": "coffee cafe espresso latte matcha cappuccino",
}

CUISINE_MIN_THRESHOLDS = {
    "american": 0.52,
}

CONTENT_TYPE_REFERENCES = {
    "food_spot": "restaurant cafe food location venue dining",
    "event": "event festival market popup concert live music opening grand opening",
    "activity": "museum experience arcade exhibit show walk park trail",
    "mixed": "content multiple activities food and activity",
}


class NPLRefiner:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name, device=device)

        print("Embedding reference categories...")
        self.meal_labels = list(MEAL_TYPE_REFERENCES.keys())
        self.meal_embeddings = self.model.encode(
            list(MEAL_TYPE_REFERENCES.values()), convert_to_tensor=True
        )

        self.cuisine_labels = list(CUISINE_TYPE_REFERENCES.keys())
        self.cuisine_embeddings = self.model.encode(
            list(CUISINE_TYPE_REFERENCES.values()), convert_to_tensor=True
        )

        self.content_labels = list(CONTENT_TYPE_REFERENCES.keys())
        self.content_embeddings = self.model.encode(
            list(CONTENT_TYPE_REFERENCES.values()), convert_to_tensor=True
        )

    def embed_text(self, text: str) -> Any:
        return self.model.encode(text or "", convert_to_tensor=True)

    def refine_meal_type(
        self, text: str, baseline_label: str, baseline_confidence: float
    ) -> Tuple[str, float, Dict[str, Any]]:
        text_embedding = self.embed_text(text)
        similarities = util.cos_sim(text_embedding, self.meal_embeddings)[0]

        top_idx = similarities.argmax().item()
        top_label = self.meal_labels[top_idx]
        top_score = float(similarities[top_idx].item())

        evidence = {
            "embedding_label": top_label,
            "embedding_similarity": round(top_score, 3),
            "baseline_label": baseline_label,
            "baseline_confidence": baseline_confidence,
            "override": False,
            "reason": "",
        }

        if top_score < 0.30:
            refined_label = baseline_label
            refined_confidence = baseline_confidence * 0.9
            evidence["reason"] = "weak_embedding_match_keep_baseline"
        elif top_label == baseline_label:
            refined_label = top_label
            refined_confidence = min(baseline_confidence * 0.95 + top_score * 0.05, 0.95)
            evidence["reason"] = "embedding_agrees_boost_baseline"
        elif top_score > 0.68 and baseline_label != "unknown" and baseline_confidence < 0.55:
            refined_label = top_label
            refined_confidence = min(top_score, 0.90)
            evidence["override"] = True
            evidence["reason"] = "strong_embedding_override_weak_baseline"
        else:
            refined_label = baseline_label
            refined_confidence = baseline_confidence * 0.85
            evidence["reason"] = "embedding_disagrees_but_baseline_sufficient"

        return refined_label, refined_confidence, evidence

    def refine_cuisines(
        self, text: str, baseline_cuisines: List[str]
    ) -> Tuple[List[str], Dict[str, Any]]:
        text_embedding = self.embed_text(text)
        similarities = util.cos_sim(text_embedding, self.cuisine_embeddings)[0]

        threshold = 0.42
        refined: List[str] = []
        sim_map: Dict[str, float] = {}

        for idx, score in enumerate(similarities):
            score_value = float(score.item())
            cuisine = self.cuisine_labels[idx]
            cuisine_threshold = CUISINE_MIN_THRESHOLDS.get(cuisine, threshold)
            if score_value > cuisine_threshold:
                refined.append(cuisine)
                sim_map[cuisine] = round(score_value, 3)

        baseline_set = set(baseline_cuisines)
        refined_set = set(refined)

        evidence = {
            "embedding_cuisines": sorted(refined),
            "embedding_similarities": sim_map,
            "baseline_cuisines": sorted(baseline_cuisines),
            "newly_detected": sorted(refined_set - baseline_set),
            "removed": sorted(baseline_set - refined_set),
            "reason": "",
        }

        best_similarity = max(sim_map.values()) if sim_map else 0.0

        if not refined:
            refined = baseline_cuisines
            evidence["reason"] = "no_strong_embedding_matches_keep_baseline"
        elif (
            baseline_set
            and refined_set != baseline_set
            and refined_set.isdisjoint(baseline_set)
            and best_similarity < 0.52
        ):
            refined = sorted(baseline_set | refined_set)
            evidence["reason"] = "embedding_disagrees_with_baseline_merge_labels"
        elif refined_set == baseline_set:
            evidence["reason"] = "embedding_confirms_baseline"
        else:
            evidence["reason"] = "embedding_refined_cuisine_list"

        return sorted(set(refined)), evidence

    def refine_content_type(
        self, text: str, baseline_label: str, baseline_confidence: float
    ) -> Tuple[str, float, Dict[str, Any]]:
        text_embedding = self.embed_text(text)
        similarities = util.cos_sim(text_embedding, self.content_embeddings)[0]

        top_idx = similarities.argmax().item()
        top_label = self.content_labels[top_idx]
        top_score = float(similarities[top_idx].item())

        ranked = sorted(
            ((self.content_labels[idx], float(score.item())) for idx, score in enumerate(similarities)),
            key=lambda pair: pair[1],
            reverse=True,
        )
        second_label, second_score = ranked[1] if len(ranked) > 1 else ("", 0.0)
        margin = top_score - second_score

        evidence = {
            "embedding_label": top_label,
            "embedding_similarity": round(top_score, 3),
            "second_label": second_label,
            "second_similarity": round(second_score, 3),
            "margin": round(margin, 3),
            "baseline_label": baseline_label,
            "baseline_confidence": baseline_confidence,
            "override": False,
            "reason": "",
        }

        if top_score < 0.40:
            refined_label = baseline_label
            refined_confidence = baseline_confidence * 0.90
            evidence["reason"] = "weak_embedding_match_keep_baseline"
        elif top_label == baseline_label:
            refined_label = top_label
            refined_confidence = min(baseline_confidence * 0.95 + top_score * 0.05, 0.95)
            evidence["reason"] = "embedding_agrees_boost_baseline"
        elif (
            top_score > 0.67
            and margin >= 0.08
            and baseline_label != "mixed"
            and baseline_confidence < 0.80
        ):
            refined_label = top_label
            refined_confidence = min(top_score, 0.88)
            evidence["override"] = True
            evidence["reason"] = "very_strong_embedding_override"
        else:
            refined_label = baseline_label
            refined_confidence = baseline_confidence * 0.90
            evidence["reason"] = "embedding_disagrees_but_baseline_acceptable"

        return refined_label, refined_confidence, evidence


def fetch_baseline_enrichments(
    conn: sqlite3.Connection, limit: Optional[int] = None
) -> List[sqlite3.Row]:
    query = """
        SELECT
            e.post_id,
            e.category,
            e.confidence,
            e.entities_json,
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
        WHERE e.model_version = 'rules-food-events-v1'
        ORDER BY p.datetime_utc DESC
    """
    if limit:
        query += f"\nLIMIT {limit}"

    cursor = conn.execute(query)
    return cursor.fetchall()


def build_text_blob(caption: str, transcript: str, hashtags: str, mentions: str) -> str:
    parts = [caption or "", transcript or "", hashtags or "", mentions or ""]
    return "\n".join(p for p in parts if p).lower()


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


def _has_food_signals(meal_type: str, cuisines: List[str]) -> bool:
    return meal_type != "unknown" or bool(cuisines)


def _resolve_content_and_category(
    baseline_meal: str,
    baseline_cuisines: List[str],
    refined_meal: str,
    refined_cuisines: List[str],
    refined_content: str,
    content_evidence: Dict[str, Any],
) -> Tuple[str, str, str]:
    has_food_signal = _has_food_signals(baseline_meal, baseline_cuisines) or _has_food_signals(refined_meal, refined_cuisines)

    adjusted_content = refined_content
    adjustment_reason = "none"

    embedding_label = str(content_evidence.get("embedding_label", ""))
    embedding_similarity = float(content_evidence.get("embedding_similarity", 0.0) or 0.0)

    if adjusted_content == "activity" and has_food_signal:
        if embedding_label == "food_spot" and embedding_similarity >= 0.35:
            adjusted_content = "food_spot"
            adjustment_reason = "activity_to_food_spot_due_food_signals"

    if adjusted_content == "event":
        category = "event"
    elif adjusted_content == "activity" and not has_food_signal:
        category = "activity"
    else:
        category = refined_meal if refined_meal != "unknown" else "unknown"

    return adjusted_content, category, adjustment_reason


def refine_posts(
    conn: sqlite3.Connection,
    refiner: NPLRefiner,
    limit: Optional[int] = None,
    all_posts: bool = False,
) -> int:
    rows = fetch_baseline_enrichments(conn, limit=None if all_posts else limit)
    total = len(rows)

    if not total:
        print("No baseline enrichments found to refine.")
        return 0

    print(f"Refining {total} posts...")

    cursor = conn.cursor()
    count = 0

    for idx, row in enumerate(rows, 1):
        post_id = row["post_id"]
        text_blob = build_text_blob(
            row["caption"], row["transcript"], row["hashtags"], row["mentions"]
        )

        entities = _safe_entities(row["entities_json"])
        baseline_meal = entities.get("meal_type", "unknown")
        baseline_cuisines = entities.get("cuisines", [])
        baseline_content = entities.get("content_type", "mixed")
        baseline_confidence = float(row["confidence"] or 0.0)

        refined_meal, meal_conf, meal_evidence = refiner.refine_meal_type(
            text_blob, baseline_meal, baseline_confidence
        )
        refined_cuisines, cuisine_evidence = refiner.refine_cuisines(
            text_blob, baseline_cuisines
        )
        refined_content, content_conf, content_evidence = refiner.refine_content_type(
            text_blob, baseline_content, baseline_confidence
        )

        resolved_content, refined_category, adjustment_reason = _resolve_content_and_category(
            baseline_meal=baseline_meal,
            baseline_cuisines=baseline_cuisines,
            refined_meal=refined_meal,
            refined_cuisines=refined_cuisines,
            refined_content=refined_content,
            content_evidence=content_evidence,
        )
        refined_content = resolved_content

        final_confidence = (meal_conf + content_conf) / 2

        needs_review = (
            refined_category != row["category"]
            or abs(final_confidence - baseline_confidence) > 0.15
            or (
                float(content_evidence.get("embedding_similarity", 0.0) or 0.0) < 0.42
                and str(content_evidence.get("embedding_label", "")) != baseline_content
            )
        )

        refined_entities = {
            "meal_type": refined_meal,
            "cuisines": refined_cuisines,
            "content_type": refined_content,
            "location": {"name": row["location_name"], "slug": None},
            "signals": {
                "meal_evidence": meal_evidence,
                "cuisine_evidence": cuisine_evidence,
                "content_evidence": content_evidence,
            },
            "metadata": {
                "hashtags": [item for item in (row["hashtags"] or "").split("|") if item],
                "mentions": [item for item in (row["mentions"] or "").split("|") if item],
                "refined_from": "rules-food-events-v1",
            },
            "refinement": {
                "meal_type_evidence": meal_evidence,
                "cuisine_evidence": cuisine_evidence,
                "content_type_evidence": content_evidence,
                "needs_review": needs_review,
                "category_adjustment_reason": adjustment_reason,
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
                post_id,
                "nlp-refined-v1",
                refined_category,
                round(final_confidence, 3),
                row["location_name"],
                json.dumps(refined_entities, ensure_ascii=False),
            ),
        )

        count += 1
        if idx % 50 == 0:
            print(f"  [{idx}/{total}] Refined {idx} posts...")
            conn.commit()

    conn.commit()
    print("Refined {} posts. Stored in nlp_enrichments with model_version='nlp-refined-v1'".format(count))
    return count


def export_refinement_report(conn: sqlite3.Connection, output_csv: Path) -> None:
    query = """
        SELECT
            b.post_id,
            p.permalink,
            b.category AS baseline_category,
            b.confidence AS baseline_confidence,
            r.category AS refined_category,
            r.confidence AS refined_confidence,
            CASE
                WHEN b.category != r.category THEN 'CHANGED'
                WHEN ABS(b.confidence - r.confidence) > 0.01 THEN 'CONFIDENCE_UPDATED'
                ELSE 'NO_CHANGE'
            END AS change_type,
            ROUND(r.confidence - b.confidence, 3) AS confidence_delta,
            b.entities_json AS baseline_entities,
            r.entities_json AS refined_entities
        FROM nlp_enrichments b
        JOIN nlp_enrichments r
            ON b.post_id = r.post_id
        JOIN normalized_posts p
            ON p.post_id = b.post_id
        WHERE b.model_version = 'rules-food-events-v1'
          AND r.model_version = 'nlp-refined-v1'
        ORDER BY change_type, confidence_delta DESC
    """

    rows = conn.execute(query).fetchall()
    if not rows:
        print("No refinements to report.")
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
        row_dict["needs_review"] = bool(_extract_nested_field(row_dict.get("refined_entities"), ["refinement", "needs_review"], False))
        row_dict["category_adjustment_reason"] = _extract_nested_field(
            row_dict.get("refined_entities"), ["refinement", "category_adjustment_reason"], ""
        )
        export_rows.append(row_dict)

    with open(output_csv, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(export_rows[0].keys()))
        writer.writeheader()
        for row in export_rows:
            writer.writerow(row)

    print(f"Refinement report: {output_csv}")

    changes: Dict[str, int] = {}
    for row in rows:
        change_type = row["change_type"]
        changes[change_type] = changes.get(change_type, 0) + 1

    print("\nRefinement Summary:")
    for change_type, count in sorted(changes.items()):
        print(f"  {change_type}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refine baseline classifications using semantic embeddings"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("nlp_processor/storage/social_media.db"),
        help="SQLite database path",
    )
    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformers model ID (default: all-MiniLM-L6-v2)",
    )
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Device for embeddings")
    parser.add_argument("--limit", type=int, help="Max posts to refine (for testing)")
    parser.add_argument("--all", action="store_true", help="Refine all baseline enrichments")
    parser.add_argument("--output-csv", type=Path, help="Export comparison report to CSV")

    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}")
        return

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    try:
        refiner = NPLRefiner(model_name=args.model, device=args.device)
        refine_posts(conn, refiner, limit=args.limit, all_posts=args.all)
        if args.output_csv:
            export_refinement_report(conn, args.output_csv)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
