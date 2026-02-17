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
