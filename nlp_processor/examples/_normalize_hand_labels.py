import csv
from pathlib import Path

src = Path('nlp_processor/examples/hand_labeled_posts_clean.csv')
out = Path('nlp_processor/examples/hand_labeled_posts_final.csv')

with src.open('r', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

fieldnames = ['permalink','meal_type','cuisines','content_type','is_unclear','notes','is_hand_labeled']

with out.open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        content_raw = (row.get('event_type') or '').strip().lower()
        content_type = ''
        if 'event' in content_raw:
            content_type = 'event'
        elif 'food_spot' in content_raw:
            content_type = 'food_spot'
        elif 'activity' in content_raw:
            content_type = 'activity'
        elif 'mixed' in content_raw:
            content_type = 'mixed'

        is_unclear = ''
        notes = (row.get('notes') or '').strip()
        if 'ambiguous' in notes.lower() or 'idk' in notes.lower():
            is_unclear = 'TRUE'

        writer.writerow({
            'permalink': (row.get('permalink') or '').strip(),
            'meal_type': (row.get('meal_type') or '').strip(),
            'cuisines': (row.get('cuisines') or '').strip(),
            'content_type': content_type,
            'is_unclear': is_unclear,
            'notes': notes,
            'is_hand_labeled': (row.get('is_hand_labeled') or 'TRUE').strip() or 'TRUE',
        })

print('rows', len(rows))
print('out', out)
