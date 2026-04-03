# AI Workflow Instructions

This document provides instructions for an LLM to understand how to build, run, and test this project. It explains the project structure, required dependencies, and how to run each stage of the processing pipeline.

---

## Project Overview

This project extracts useful information from short-form social media content and organizes it into structured data.

The system currently processes Instagram Reel metadata using the following pipeline:

Instagram scraper output (Instaloader JSON)  
→ metadata parser  
→ structured dataset (NDJSON / CSV)  
→ SQLite storage  
→ NLP processing (entity extraction + classification)  
→ API access to stored information

The goal of the system is to identify useful entities such as locations mentioned in short-form videos and organize them so they are easier to browse and retrieve later.

---

## Repository Structure


social_media_organizer/
│
├── nlp_processor/
│ ├── instagram_parser.py
│ ├── processor.py
│ ├── sqlite_loader.py
│ ├── schema.py
│ └── examples/
│
├── app/
│ ├── main.py
│ ├── ingest.py
│ ├── classifier.py
│ ├── db.py
│ └── schemas.py
│
├── storage/
│ └── schema.sql
│
└── README.md


### Key Components

**instagram_parser.py**  
Parses Instaloader JSON exports and extracts useful metadata fields such as captions, hashtags, tagged users, timestamps, and engagement metrics.

**sqlite_loader.py**  
Loads parsed metadata records into normalized SQLite tables.

**processor.py**  
Placeholder NLP pipeline used to perform entity extraction and classification.

**main.py**  
FastAPI server that exposes endpoints for ingesting and retrieving processed data.

---

## Requirements

Recommended Python version:


Python 3.10+


Install dependencies:


pip install -r requirements.txt


If a requirements file is not present, install the basic dependencies:


pip install fastapi uvicorn pydantic sqlalchemy


---

## Running the Data Pipeline

### 1. Collect Instagram Metadata

Use Instaloader to download metadata from a public Instagram account.

Example:


instaloader profile atllovesmo


This produces JSON files containing metadata for posts and reels.

---

### 2. Parse Instagram Scraper Output

Run the parser to extract useful metadata from the Instaloader JSON files.


python -m nlp_processor.instagram_parser
--input atllovesmo
--output nlp_processor/examples/instagram_posts.ndjson
--csv-output nlp_processor/examples/instagram_posts.csv


The parser extracts fields such as:

- caption text
- hashtags
- tagged accounts
- timestamps
- engagement metrics
- location metadata (if available)

The output is saved as structured NDJSON and CSV files.

---

### 3. Load Parsed Data into SQLite

After parsing the metadata, load the structured records into the SQLite database.


python -m nlp_processor.sqlite_loader
--input nlp_processor/examples/instagram_posts.ndjson
--db nlp_processor/storage/social_media.db
--schema nlp_processor/storage/schema.sql


This step creates normalized tables including:

- normalized_posts
- post_hashtags
- post_mentions
- post_tagged_users

These tables allow the system to query metadata efficiently.

---

### 4. Run the API Server

Start the FastAPI server:


uvicorn app.main:app --reload


The API will be available at:


http://localhost:8000


---

## API Endpoints

### Health Check


GET /health


Example response:


{"status": "ok"}


---

### Ingest Metadata


POST /ingest


Example request body:


{
"url": "https://instagram.com/example
",
"caption": "Best coffee shop in Atlanta",
"hashtags": "#coffee #atlanta",
"transcript": null
}


---

### Retrieve Stored Locations


GET /locations


Returns location entries detected by the classifier.

---

## NLP Processing (Current State)

The current NLP implementation is a placeholder and performs:

- simple keyword classification
- basic entity extraction using rule-based patterns

Future improvements may include:

- spaCy named entity recognition
- location geocoding
- improved classification models
- additional metadata features

---

## Testing the System

A minimal test workflow:

1. Download Instagram metadata using Instaloader.
2. Run the parser to convert the JSON metadata into structured records.
3. Load the parsed records into the SQLite database.
4. Start the FastAPI server.
5. Send requests to the API endpoints to confirm the pipeline is working.

---

## Future Improvements

Planned improvements include:

- replacing heuristic NLP methods with spaCy models
- adding geocoding for detected locations
- supporting additional platforms such as TikTok
- building a dashboard to visualize organized results
