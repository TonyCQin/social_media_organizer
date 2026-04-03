import sqlite3

conn = sqlite3.connect('nlp_processor/storage/social_media.db')
c = conn.cursor()

# Add url_status column if missing
try:
    c.execute('ALTER TABLE normalized_posts ADD COLUMN url_status TEXT DEFAULT "unchecked"')
    print('✓ Added url_status column to normalized_posts')
except sqlite3.OperationalError as e:
    print(f'ℹ url_status column already exists')

# Create video_transcripts table
c.execute('''
CREATE TABLE IF NOT EXISTS video_transcripts (
    post_id TEXT PRIMARY KEY,
    video_url TEXT,
    transcript TEXT,
    confidence REAL,
    model_version TEXT NOT NULL,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES normalized_posts(post_id) ON DELETE CASCADE
)
''')
print('✓ Created video_transcripts table')

c.execute('CREATE INDEX IF NOT EXISTS idx_video_transcripts_model ON video_transcripts(model_version)')
print('✓ Created index on video_transcripts(model_version)')

conn.commit()
conn.close()
print('Schema update complete!')
