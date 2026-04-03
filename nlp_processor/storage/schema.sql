PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_instagram_posts (
    post_id TEXT PRIMARY KEY,
    shortcode TEXT UNIQUE,
    source_file TEXT,
    raw_json TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS normalized_posts (
    post_id TEXT PRIMARY KEY,
    shortcode TEXT UNIQUE,
    permalink TEXT,
    typename TEXT,
    product_type TEXT,
    is_video INTEGER,
    timestamp_utc INTEGER,
    datetime_utc TEXT,
    caption TEXT,
    caption_word_count INTEGER,
    owner_id TEXT,
    owner_username TEXT,
    owner_full_name TEXT,
    owner_is_verified INTEGER,
    location_id TEXT,
    location_name TEXT,
    location_slug TEXT,
    likes INTEGER,
    comments INTEGER,
    video_views INTEGER,
    display_url TEXT,
    thumbnail_src TEXT,
    video_url TEXT,
    video_duration REAL,
    sidecar_items INTEGER,
    text_for_nlp TEXT,
    source_file TEXT,
    parser_version TEXT NOT NULL,
    ingest_status TEXT NOT NULL DEFAULT 'ingested',
    nlp_status TEXT NOT NULL DEFAULT 'pending',
    url_status TEXT DEFAULT 'unchecked',
    last_error TEXT,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_normalized_posts_datetime ON normalized_posts(datetime_utc);
CREATE INDEX IF NOT EXISTS idx_normalized_posts_location ON normalized_posts(location_name);
CREATE INDEX IF NOT EXISTS idx_normalized_posts_owner ON normalized_posts(owner_username);
CREATE INDEX IF NOT EXISTS idx_normalized_posts_nlp_status ON normalized_posts(nlp_status);

CREATE TABLE IF NOT EXISTS post_hashtags (
    post_id TEXT NOT NULL,
    hashtag TEXT NOT NULL,
    PRIMARY KEY (post_id, hashtag),
    FOREIGN KEY (post_id) REFERENCES normalized_posts(post_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS post_mentions (
    post_id TEXT NOT NULL,
    mention TEXT NOT NULL,
    PRIMARY KEY (post_id, mention),
    FOREIGN KEY (post_id) REFERENCES normalized_posts(post_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS post_tagged_users (
    post_id TEXT NOT NULL,
    tagged_username TEXT NOT NULL,
    PRIMARY KEY (post_id, tagged_username),
    FOREIGN KEY (post_id) REFERENCES normalized_posts(post_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS nlp_enrichments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    category TEXT,
    confidence REAL,
    place_name TEXT,
    entities_json TEXT,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (post_id, model_version),
    FOREIGN KEY (post_id) REFERENCES normalized_posts(post_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS video_transcripts (
    post_id TEXT PRIMARY KEY,
    video_url TEXT,
    transcript TEXT,
    confidence REAL,
    model_version TEXT NOT NULL,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES normalized_posts(post_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_video_transcripts_model ON video_transcripts(model_version);
