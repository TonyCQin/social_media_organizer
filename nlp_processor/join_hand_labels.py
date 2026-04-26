import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse, urlunparse


def normalize_permalink(permalink: str) -> str:
    value = (permalink or "").strip()
    if not value:
        return ""

    parsed = urlparse(value)
    if not parsed.scheme and not parsed.netloc:
        path = value.split("?", 1)[0].split("#", 1)[0]
        path = path.rstrip("/")
        return f"{path}/" if path else ""

    normalized = parsed._replace(
        scheme=parsed.scheme.lower() or "https",
        netloc=parsed.netloc.lower(),
        params="",
        query="",
        fragment="",
    )
    normalized_url = urlunparse(normalized)
    return normalized_url.rstrip("/") + "/"


def read_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def build_prediction_index(
    prediction_rows: List[Dict[str, str]],
    prediction_permalink_col: str,
) -> Tuple[Dict[str, Dict[str, str]], int]:
    index: Dict[str, Dict[str, str]] = {}
    duplicate_keys = 0

    for row in prediction_rows:
        key = normalize_permalink(row.get(prediction_permalink_col, ""))
        if not key:
            continue
        if key in index:
            duplicate_keys += 1
            continue
        index[key] = row

    return index, duplicate_keys


def join_rows(
    hand_rows: List[Dict[str, str]],
    prediction_index: Dict[str, Dict[str, str]],
    hand_permalink_col: str,
    hand_cuisine_col: str,
    hand_meal_col: str,
    hand_content_col: str,
) -> Tuple[List[Dict[str, str]], int, int]:
    merged_rows: List[Dict[str, str]] = []
    matched_count = 0
    unmatched_count = 0

    for hand_row in hand_rows:
        raw_permalink = hand_row.get(hand_permalink_col, "")
        permalink_key = normalize_permalink(raw_permalink)
        prediction_row = prediction_index.get(permalink_key)

        if prediction_row:
            merged = dict(prediction_row)
            merged["human_permalink"] = raw_permalink
            merged["human_cuisine"] = hand_row.get(hand_cuisine_col, "")
            merged["human_meal_type"] = hand_row.get(hand_meal_col, "")
            merged["human_content_type"] = hand_row.get(hand_content_col, "")
            merged["is_hand_labeled"] = hand_row.get("is_hand_labeled", "TRUE")
            merged["join_status"] = "matched"
            matched_count += 1
        else:
            merged = {
                "human_permalink": raw_permalink,
                "human_cuisine": hand_row.get(hand_cuisine_col, ""),
                "human_meal_type": hand_row.get(hand_meal_col, ""),
                "human_content_type": hand_row.get(hand_content_col, ""),
                "is_hand_labeled": hand_row.get("is_hand_labeled", "TRUE"),
                "join_status": "unmatched",
            }
            unmatched_count += 1

        merged_rows.append(merged)

    return merged_rows, matched_count, unmatched_count


def write_csv_rows(output_csv: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", encoding="utf-8", newline="") as file:
            file.write("")
        return

    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Join hand-labeled cuisine/meal CSV with prediction CSV using permalink."
    )
    parser.add_argument(
        "--hand-labels-csv",
        type=Path,
        required=True,
        help="CSV with your manual labels (must contain permalink and label columns).",
    )
    parser.add_argument(
        "--prediction-csv",
        type=Path,
        required=True,
        help="Existing prediction CSV (e.g., refinement_comparison_full_v4.csv or post_categories report).",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        required=True,
        help="Where to write merged output CSV.",
    )
    parser.add_argument(
        "--hand-permalink-col",
        default="permalink",
        help="Permalink column in hand-label CSV (default: permalink).",
    )
    parser.add_argument(
        "--prediction-permalink-col",
        default="permalink",
        help="Permalink column in prediction CSV (default: permalink).",
    )
    parser.add_argument(
        "--hand-cuisine-col",
        default="cuisine",
        help="Cuisine column in hand-label CSV (default: cuisine).",
    )
    parser.add_argument(
        "--hand-meal-col",
        default="meal_type",
        help="Meal-type column in hand-label CSV (default: meal_type).",
    )
    parser.add_argument(
        "--hand-content-col",
        default="content_type",
        help="Content-type column in hand-label CSV (default: content_type).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.hand_labels_csv.exists():
        raise FileNotFoundError(f"Hand-label CSV not found: {args.hand_labels_csv}")
    if not args.prediction_csv.exists():
        raise FileNotFoundError(f"Prediction CSV not found: {args.prediction_csv}")

    hand_rows = read_csv_rows(args.hand_labels_csv)
    prediction_rows = read_csv_rows(args.prediction_csv)

    prediction_index, duplicate_keys = build_prediction_index(
        prediction_rows=prediction_rows,
        prediction_permalink_col=args.prediction_permalink_col,
    )

    merged_rows, matched_count, unmatched_count = join_rows(
        hand_rows=hand_rows,
        prediction_index=prediction_index,
        hand_permalink_col=args.hand_permalink_col,
        hand_cuisine_col=args.hand_cuisine_col,
        hand_meal_col=args.hand_meal_col,
        hand_content_col=args.hand_content_col,
    )

    write_csv_rows(args.output_csv, merged_rows)

    print(f"Hand-label rows: {len(hand_rows)}")
    print(f"Prediction rows: {len(prediction_rows)}")
    print(f"Prediction permalink duplicates skipped: {duplicate_keys}")
    print(f"Matched: {matched_count}")
    print(f"Unmatched: {unmatched_count}")
    print(f"Merged output: {args.output_csv}")


if __name__ == "__main__":
    main()
