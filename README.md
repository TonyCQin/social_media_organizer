# social_media_organizer

## Current utility scripts

- `nlp_processor/instagram_parser.py` parses Instaloader `.json` and `.json.xz` files and outputs normalized post metadata for NLP/pipeline work.

Example:

```bash
python -m nlp_processor.instagram_parser --input atllovesmo --limit 25 --output nlp_processor/examples/instagram_posts.ndjson
```

With CSV output:

```bash
python -m nlp_processor.instagram_parser --input atllovesmo --limit 25 --output nlp_processor/examples/instagram_posts.ndjson --csv-output nlp_processor/examples/instagram_posts.csv
```

## Storage pipeline (SQLite)

Load parsed records into SQLite:

```bash
python -m nlp_processor.sqlite_loader --input nlp_processor/examples/instagram_posts.ndjson --db nlp_processor/storage/social_media.db --schema nlp_processor/storage/schema.sql --parser-version instagram_parser_v1
```

Check ingestion stats:

```bash
python -m nlp_processor.db_summary --db nlp_processor/storage/social_media.db
```

## LLM contextual refinement layer

After running baseline + NLP refinement, you can run a post-level LLM pass for richer contextual labeling.

Dry run (no API calls, verifies pipeline wiring):

```bash
python -m nlp_processor.llm_refine_posts --db nlp_processor/storage/social_media.db --dry-run --output-csv nlp_processor/examples/llm_refinement_comparison_dryrun.csv
```

Real run (OpenAI-compatible API):

```bash
set OPENAI_API_KEY=YOUR_KEY
python -m nlp_processor.llm_refine_posts --db nlp_processor/storage/social_media.db --source-model-version nlp-refined-v1 --output-model-version llm-refined-v1 --llm-model gpt-4.1-mini --output-csv nlp_processor/examples/llm_refinement_comparison.csv
```

Then you can join against hand labels as usual:

```bash
python nlp_processor/join_hand_labels.py --hand-labels-csv nlp_processor/examples/hand_labeled_posts.csv --prediction-csv nlp_processor/examples/llm_refinement_comparison.csv --output-csv nlp_processor/examples/llm_refinement_with_hand_labels.csv --hand-permalink-col permalink --hand-cuisine-col cuisines --hand-meal-col meal_type --hand-content-col content_type
```

## One canonical final results table

To create a single queryable table across model layers (priority: `llm-refined-v1` > `nlp-refined-v1` > `rules-food-events-v1`):

```bash
python nlp_processor/refresh_final_results_table.py --db nlp_processor/storage/social_media.db
```

To export that table into readable CSV files:

```bash
python nlp_processor/export_final_results_csv.py --db nlp_processor/storage/social_media.db
```

This refreshes `final_post_classifications` in SQLite with one row per `post_id`.

Example queries:

```sql
SELECT post_id, final_model_version, category, meal_type, cuisines, content_type, confidence
FROM final_post_classifications
ORDER BY datetime_utc DESC
LIMIT 25;
```

```sql
SELECT category, COUNT(*)
FROM final_post_classifications
GROUP BY category
ORDER BY COUNT(*) DESC;
```

```sql
SELECT final_model_version, COUNT(*)
FROM final_post_classifications
GROUP BY final_model_version
ORDER BY COUNT(*) DESC;
```