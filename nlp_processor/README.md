# NLP Processor

This package will hold the NLP processing pipeline. For now it contains a minimal, local stub that accepts a JSON-like dictionary describing a short-form video (metadata only), validates the input with Pydantic, and runs placeholder processing steps (entity extraction and simple classification).

Purpose:
- Central location for all NLP code: NER, classification, geocoding, and other enrichment.
- Input (for now): a JSON/dict with video metadata. Exact format to be decided; a recommended minimal schema is shown in `schema.py`.

Files added:
- `schema.py` — `VideoData` Pydantic model describing the expected JSON fields
- `processor.py` — `process_video_json(payload)` function that accepts a dict and returns a processed dict (placeholder logic)

Next work:
- Replace placeholder heuristics with spaCy / transformers for NER
- Add geocoding (Nominatim or Google Maps) to turn place names into coordinates
- Add background task queue for long-running steps (download/transcribe)

## Instagram metadata parser

`instagram_parser.py` parses Instaloader exports (`.json` and `.json.xz`) and extracts the most useful fields for downstream NLP and organization.

Extracted fields include:
- Post identifiers: `id`, `shortcode`, `permalink`
- Post metadata: `typename`, `product_type`, `is_video`, timestamp fields
- NLP text fields: `caption`, `hashtags`, `caption_mentions`, `text_for_nlp`
- Context entities: tagged usernames, owner profile fields, location fields
- Engagement/media: likes, comments, video views, media URLs, video duration

Quick run from repo root:

```bash
python -m nlp_processor.instagram_parser --input atllovesmo --limit 10 --pretty --output nlp_processor/examples/instagram_posts_sample.json
```

Generate both NDJSON and CSV:

```bash
python -m nlp_processor.instagram_parser --input atllovesmo --output nlp_processor/examples/instagram_posts.ndjson --csv-output nlp_processor/examples/instagram_posts.csv
```

Default output format is NDJSON (one JSON object per line), which is pipeline-friendly for future SQLite/API ingestion.

Notes:
- If both `file.json` and `file.json.xz` exist, the parser keeps only one record and prefers `.json.xz`.
- Non-post Instaloader metadata files (for example iterator/profile snapshots) are skipped.

## Storage + ingestion pipeline (Checkpoint 3)

This project now includes an initial SQLite-backed ingestion layer:

- `storage/schema.sql` — normalized storage schema
- `sqlite_loader.py` — loads parser output (`.ndjson` or `.csv`) into SQLite
- `db_summary.py` — quick health/stats checks on ingested data

### End-to-end commands

1) Parse Instagram exports to NDJSON/CSV:

```bash
python -m nlp_processor.instagram_parser --input atllovesmo --output nlp_processor/examples/instagram_posts.ndjson --csv-output nlp_processor/examples/instagram_posts.csv
```

2) Load NDJSON into SQLite:

```bash
python -m nlp_processor.sqlite_loader --input nlp_processor/examples/instagram_posts.ndjson --db nlp_processor/storage/social_media.db --schema nlp_processor/storage/schema.sql --parser-version instagram_parser_v1
```

3) Inspect summary stats:

```bash
python -m nlp_processor.db_summary --db nlp_processor/storage/social_media.db
```

### Current table design

- `raw_instagram_posts`: lineage and stored raw record JSON from parser output
- `normalized_posts`: one row per post with flattened core metadata and pipeline statuses
- `post_hashtags`, `post_mentions`, `post_tagged_users`: normalized multi-value fields
- `nlp_enrichments`: versioned NLP output table for later milestone integration

## Video URL validation + MP4 transcription

For video-oriented processing, two scripts are included:

- `check_video_urls.py`: validates existing `video_url` values and updates `normalized_posts.url_status`
- `transcribe_mp4s.py`: transcribes local `.mp4` files and stores text in `video_transcripts`

Install dependencies:

```bash
pip install -r nlp_processor/requirements.txt
```

Validate video URLs (sample run):

```bash
python -m nlp_processor.check_video_urls --db nlp_processor/storage/social_media.db --limit 25 --delay 0.2 --report-csv nlp_processor/examples/video_url_validation_report.csv
```

Transcribe local MP4 files (sample run):

```bash
python -m nlp_processor.transcribe_mp4s --mp4-dir atllovesmo --db nlp_processor/storage/social_media.db --model tiny --limit 3 --output-dir nlp_processor/examples/transcripts
```

## Metadata-based post categorization

`categorize_posts.py` classifies posts using caption/hashtags/mentions/transcript/location metadata.

Current rule taxonomy:

- Meal type: `breakfast`, `brunch`, `lunch`, `dinner`, `dessert`, `drinks`, `snack`, `unknown`
- Cuisine (multi-label): e.g. `mexican`, `italian`, `japanese`, `korean`, `vegan`, `coffee_cafe`
- Content type: `food_spot`, `event`, `activity`, `mixed`

The script writes:

- DB upserts into `nlp_enrichments` with model version tag
- post status updates in `normalized_posts.nlp_status = 'categorized'`
- CSV report for review/demo output

Sample run:

```bash
python -m nlp_processor.categorize_posts --db nlp_processor/storage/social_media.db --limit 25 --model-version rules-food-events-v1 --output-csv nlp_processor/examples/post_categories_report_sample.csv
```
