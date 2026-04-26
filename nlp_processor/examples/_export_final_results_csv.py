import csv
import sqlite3
from pathlib import Path

base = Path("nlp_processor/examples")
base.mkdir(parents=True, exist_ok=True)

db_path = Path("nlp_processor/storage/social_media.db")
full_csv = base / "final_post_classifications.csv"
readable_csv = base / "final_post_classifications_readable.csv"

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM final_post_classifications ORDER BY datetime_utc DESC").fetchall()
if not rows:
    raise SystemExit("No rows in final_post_classifications")

fieldnames = list(rows[0].keys())
with full_csv.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(dict(r))

readable_query = '''
SELECT
    post_id,
    datetime_utc,
    permalink,
    owner_username,
    location_name,
    final_model_version,
    category,
    meal_type,
    cuisines,
    content_type,
    confidence,
    needs_review,
    rationale
FROM final_post_classifications
ORDER BY datetime_utc DESC
'''
readable_rows = conn.execute(readable_query).fetchall()
readable_fields = list(readable_rows[0].keys())
with readable_csv.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=readable_fields)
    writer.writeheader()
    for r in readable_rows:
        writer.writerow(dict(r))

print(f"full_csv={full_csv}")
print(f"readable_csv={readable_csv}")
print(f"rows={len(rows)}")
print(f"full_columns={len(fieldnames)}")
print(f"readable_columns={len(readable_fields)}")

conn.close()
