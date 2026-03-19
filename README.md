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