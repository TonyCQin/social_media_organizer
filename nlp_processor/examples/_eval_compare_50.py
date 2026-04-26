#!/usr/bin/env python3
import csv
from pathlib import Path

base_dir = Path(__file__).parent
before_path = base_dir / "refinement_with_hand_labels_50.csv"
after_path = base_dir / "refinement_with_hand_labels_50_v5.csv"


def norm(v):
    return (v or "").strip().lower()


def parse_labels(v):
    text = norm(v)
    if not text or text == "unknown":
        return set()
    for sep in [",", ";", "|"]:
        text = text.replace(sep, "|")
    return {p.strip() for p in text.split("|") if p.strip() and p.strip() != "unknown"}


def metrics(path: Path):
    rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
    meal_total = meal_correct = 0
    content_total = content_correct = 0
    true_pos = false_pos = false_neg = 0
    exact_match_total = exact_match_correct = 0

    for r in rows:
        human_meal = norm(r.get("human_meal_type"))
        pred_meal = norm(r.get("refined_meal_type") or r.get("meal_type"))
        if human_meal:
            meal_total += 1
            if human_meal == pred_meal:
                meal_correct += 1

        human_content = norm(r.get("human_content_type"))
        pred_content = norm(r.get("refined_content_type") or r.get("content_type"))
        if human_content:
            content_total += 1
            if human_content == pred_content:
                content_correct += 1

        hset = parse_labels(r.get("human_cuisine"))
        pset = parse_labels(r.get("refined_cuisines") or r.get("cuisines"))
        if hset or pset:
            exact_match_total += 1
            if hset == pset:
                exact_match_correct += 1
            true_pos += len(hset & pset)
            false_pos += len(pset - hset)
            false_neg += len(hset - pset)

    prec = true_pos / (true_pos + false_pos) if (true_pos + false_pos) else 0.0
    rec = true_pos / (true_pos + false_neg) if (true_pos + false_neg) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    return {
        "rows": len(rows),
        "meal_accuracy": meal_correct / meal_total if meal_total else 0.0,
        "content_accuracy": content_correct / content_total if content_total else 0.0,
        "cuisine_exact": exact_match_correct / exact_match_total if exact_match_total else 0.0,
        "cuisine_precision": prec,
        "cuisine_recall": rec,
        "cuisine_f1": f1,
        "meal_counts": (meal_correct, meal_total),
        "content_counts": (content_correct, content_total),
        "cuisine_counts": (exact_match_correct, exact_match_total),
    }


before = metrics(before_path)
after = metrics(after_path)

print("=" * 72)
print("50-LABEL METRICS: BEFORE (v4) vs AFTER (v5)")
print("=" * 72)


def print_line(label, before_val, after_val):
    delta = after_val - before_val
    print(f"{label:<22} {before_val:>8.4f}  ->  {after_val:>8.4f}   (Δ {delta:+.4f})")


print_line("meal_accuracy", before["meal_accuracy"], after["meal_accuracy"])
print_line("content_accuracy", before["content_accuracy"], after["content_accuracy"])
print_line("cuisine_exact", before["cuisine_exact"], after["cuisine_exact"])
print_line("cuisine_precision", before["cuisine_precision"], after["cuisine_precision"])
print_line("cuisine_recall", before["cuisine_recall"], after["cuisine_recall"])
print_line("cuisine_f1", before["cuisine_f1"], after["cuisine_f1"])

print("\nCounts:")
print(f"Meal:    {before['meal_counts'][0]}/{before['meal_counts'][1]} -> {after['meal_counts'][0]}/{after['meal_counts'][1]}")
print(f"Content: {before['content_counts'][0]}/{before['content_counts'][1]} -> {after['content_counts'][0]}/{after['content_counts'][1]}")
print(f"Cuisine exact: {before['cuisine_counts'][0]}/{before['cuisine_counts'][1]} -> {after['cuisine_counts'][0]}/{after['cuisine_counts'][1]}")
