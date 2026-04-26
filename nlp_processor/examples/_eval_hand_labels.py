import csv
from pathlib import Path

path = Path('nlp_processor/examples/refinement_with_hand_labels.csv')
rows = list(csv.DictReader(path.open('r', encoding='utf-8', newline='')))

def norm(v):
    return (v or '').strip().lower()

def parse_labels(v):
    text = norm(v)
    if not text or text == 'unknown':
        return set()
    for sep in [',',';']:
        text = text.replace(sep, '|')
    return {p.strip() for p in text.split('|') if p.strip() and p.strip() != 'unknown'}

meal_total = meal_correct = 0
content_total = content_correct = 0

true_pos = false_pos = false_neg = 0
exact_match_total = exact_match_correct = 0

for r in rows:
    human_meal = norm(r.get('human_meal_type'))
    pred_meal = norm(r.get('refined_meal_type') or r.get('meal_type'))
    if human_meal:
        meal_total += 1
        if human_meal == pred_meal:
            meal_correct += 1

    human_content = norm(r.get('human_content_type'))
    pred_content = norm(r.get('refined_content_type') or r.get('content_type'))
    if human_content:
        content_total += 1
        if human_content == pred_content:
            content_correct += 1

    hset = parse_labels(r.get('human_cuisine'))
    pset = parse_labels(r.get('refined_cuisines') or r.get('cuisines'))

    # evaluate cuisine where at least one side has cuisine signal
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

print('rows_total', len(rows))
print('meal_labeled', meal_total)
print('meal_accuracy', round(meal_correct / meal_total, 4) if meal_total else 'n/a')
print('content_labeled', content_total)
print('content_accuracy', round(content_correct / content_total, 4) if content_total else 'n/a')
print('cuisine_eval_rows', exact_match_total)
print('cuisine_exact_match', round(exact_match_correct / exact_match_total, 4) if exact_match_total else 'n/a')
print('cuisine_precision', round(prec, 4))
print('cuisine_recall', round(rec, 4))
print('cuisine_f1', round(f1, 4))
