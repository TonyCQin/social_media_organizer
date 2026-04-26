#!/usr/bin/env python3
import csv
from pathlib import Path
from collections import defaultdict

path = Path(__file__).parent / "refinement_with_hand_labels_50.csv"
rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))

def norm(v):
    return (v or "").strip().lower()

def parse_labels(v):
    text = norm(v)
    if not text or text == "unknown":
        return set()
    for sep in [",", ";", "|"]:
        text = text.replace(sep, "|")
    return {p.strip() for p in text.split("|") if p.strip() and p.strip() != "unknown"}

# Meal type errors
meal_errors = defaultdict(lambda: {"correct": 0, "total": 0, "misclassified_as": defaultdict(int)})
content_errors = defaultdict(lambda: {"correct": 0, "total": 0, "misclassified_as": defaultdict(int)})
cuisine_errors = []

print("="*70)
print("MEAL TYPE ANALYSIS")
print("="*70)

for r in rows:
    human_meal = norm(r.get("human_meal_type"))
    pred_meal = norm(r.get("refined_meal_type") or r.get("meal_type"))
    
    if human_meal:
        meal_errors[human_meal]["total"] += 1
        if human_meal == pred_meal:
            meal_errors[human_meal]["correct"] += 1
        else:
            meal_errors[human_meal]["misclassified_as"][pred_meal] += 1

for meal_type in sorted(meal_errors.keys()):
    stats = meal_errors[meal_type]
    acc = stats["correct"] / stats["total"] if stats["total"] else 0
    print(f"\n{meal_type.upper()}: {stats['correct']}/{stats['total']} correct ({acc*100:.1f}%)")
    if stats["misclassified_as"]:
        for pred, count in sorted(stats["misclassified_as"].items(), key=lambda x: -x[1]):
            print(f"  → {pred}: {count} times")

print("\n" + "="*70)
print("CONTENT TYPE ANALYSIS")
print("="*70)

for r in rows:
    human_content = norm(r.get("human_content_type"))
    pred_content = norm(r.get("refined_content_type") or r.get("content_type"))
    
    if human_content:
        content_errors[human_content]["total"] += 1
        if human_content == pred_content:
            content_errors[human_content]["correct"] += 1
        else:
            content_errors[human_content]["misclassified_as"][pred_content] += 1

for content_type in sorted(content_errors.keys()):
    stats = content_errors[content_type]
    acc = stats["correct"] / stats["total"] if stats["total"] else 0
    print(f"\n{content_type.upper()}: {stats['correct']}/{stats['total']} correct ({acc*100:.1f}%)")
    if stats["misclassified_as"]:
        for pred, count in sorted(stats["misclassified_as"].items(), key=lambda x: -x[1]):
            print(f"  → {pred}: {count} times")

print("\n" + "="*70)
print("CUISINE ANALYSIS (Posts with cuisine labels)")
print("="*70)

correct_cuisines = 0
total_with_cuisines = 0
common_fps = defaultdict(int)  # false positives
common_fns = defaultdict(int)  # false negatives

for r in rows:
    hset = parse_labels(r.get("human_cuisine"))
    pset = parse_labels(r.get("refined_cuisines") or r.get("cuisines"))
    
    if hset or pset:
        total_with_cuisines += 1
        if hset == pset:
            correct_cuisines += 1
        else:
            # Track false positives and false negatives
            for fp in (pset - hset):
                common_fps[fp] += 1
            for fn in (hset - pset):
                common_fns[fn] += 1

print(f"\nExact match accuracy: {correct_cuisines}/{total_with_cuisines} = {correct_cuisines/total_with_cuisines*100:.1f}%")

print(f"\nMost common FALSE POSITIVES (predicted but not labeled):")
for cuisine, count in sorted(common_fps.items(), key=lambda x: -x[1])[:8]:
    print(f"  {cuisine}: {count} times")

print(f"\nMost common FALSE NEGATIVES (labeled but not predicted):")
for cuisine, count in sorted(common_fns.items(), key=lambda x: -x[1])[:8]:
    print(f"  {cuisine}: {count} times")

print("\n" + "="*70)
print("PROBLEM SUMMARY")
print("="*70)

# Find worst performers
worst_meal = min(meal_errors.items(), key=lambda x: x[1]["correct"]/x[1]["total"] if x[1]["total"] else 1.0)
worst_content = min(content_errors.items(), key=lambda x: x[1]["correct"]/x[1]["total"] if x[1]["total"] else 1.0)

print(f"\nWorst meal type: {worst_meal[0]} ({worst_meal[1]['correct']}/{worst_meal[1]['total']} = {worst_meal[1]['correct']/worst_meal[1]['total']*100:.0f}%)")
print(f"Worst content type: {worst_content[0]} ({worst_content[1]['correct']}/{worst_content[1]['total']} = {worst_content[1]['correct']/worst_content[1]['total']*100:.0f}%)")
print(f"Worst cuisine false positive: {max(common_fps.items(), key=lambda x: x[1])[0]} (appears {max(common_fps.items(), key=lambda x: x[1])[1]} times)")
