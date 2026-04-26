#!/usr/bin/env python3
import csv
from pathlib import Path

path = Path(__file__).parent / "refinement_with_hand_labels_50.csv"
rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))

def norm(v):
    return (v or "").strip().lower()

print("="*80)
print("DINNER POSTS THAT WERE CLASSIFIED AS DRINKS")
print("="*80)

for i, r in enumerate(rows, 1):
    human_meal = norm(r.get("human_meal_type"))
    pred_meal = norm(r.get("refined_meal_type") or r.get("meal_type"))
    
    if human_meal == "dinner" and pred_meal == "drinks":
        caption = r.get("caption", "")[:100]
        print(f"\n[{i}] {r.get('permalink')}")
        print(f"    Caption: {caption}...")
        print(f"    Baseline: {r.get('meal_type')}")
        print(f"    Refined: {r.get('refined_meal_type') or 'N/A'}")
        print(f"    Confidence: {r.get('confidence')}")

print("\n" + "="*80)
print("AMERICAN CUISINE FALSE POSITIVES")
print("="*80)

for i, r in enumerate(rows, 1):
    human_cuisine = norm(r.get("human_cuisine", ""))
    pred_cuisine = norm(r.get("refined_cuisines") or r.get("cuisines", ""))
    
    # Check if american was predicted but not in human labels
    if "american" in pred_cuisine and ("american" not in human_cuisine and human_cuisine != ""):
        caption = r.get("caption", "")[:100]
        print(f"\n[{i}] {r.get('permalink')}")
        print(f"    Caption: {caption}...")
        print(f"    Human cuisines: {human_cuisine}")
        print(f"    Predicted cuisines: {pred_cuisine}")
