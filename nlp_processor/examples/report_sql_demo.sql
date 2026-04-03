-- CS 4365/6365 Report Demo SQL
-- Database target: nlp_processor/storage/social_media.db
--
-- Run from project root (PowerShell) with Python sqlite3:
-- python -c "import sqlite3; c=sqlite3.connect(r'nlp_processor/storage/social_media.db'); print(c.execute('SELECT COUNT(*) FROM normalized_posts').fetchone()); c.close()"
--
-- Or run these queries inside any SQLite client.

-- 1) Basic data volume checks (pipeline ingestion proof)
SELECT 'normalized_posts' AS table_name, COUNT(*) AS row_count FROM normalized_posts
UNION ALL
SELECT 'post_hashtags', COUNT(*) FROM post_hashtags
UNION ALL
SELECT 'post_mentions', COUNT(*) FROM post_mentions
UNION ALL
SELECT 'post_tagged_users', COUNT(*) FROM post_tagged_users
UNION ALL
SELECT 'raw_instagram_posts', COUNT(*) FROM raw_instagram_posts
ORDER BY table_name;

-- 2) Top locations by number of posts
SELECT
    COALESCE(location_name, '[none]') AS location_name,
    COUNT(*) AS post_count
FROM normalized_posts
GROUP BY COALESCE(location_name, '[none]')
ORDER BY post_count DESC, location_name ASC
LIMIT 15;

-- 3) Top hashtags (demonstrates normalized many-to-one schema)
SELECT
    hashtag,
    COUNT(*) AS usage_count
FROM post_hashtags
GROUP BY hashtag
ORDER BY usage_count DESC, hashtag ASC
LIMIT 20;

-- 4) Most-mentioned accounts in captions
SELECT
    mention,
    COUNT(*) AS mention_count
FROM post_mentions
GROUP BY mention
ORDER BY mention_count DESC, mention ASC
LIMIT 20;

-- 5) Engagement leaderboard (top 20 posts by likes)
SELECT
    shortcode,
    datetime_utc,
    location_name,
    likes,
    comments,
    video_views,
    substr(replace(caption, char(10), ' '), 1, 120) AS caption_preview
FROM normalized_posts
ORDER BY COALESCE(likes, 0) DESC, COALESCE(comments, 0) DESC
LIMIT 20;

-- 6) Video vs non-video distribution
SELECT
    CASE WHEN is_video = 1 THEN 'video' ELSE 'non_video' END AS media_type,
    COUNT(*) AS total_posts,
    ROUND(AVG(COALESCE(likes, 0)), 2) AS avg_likes,
    ROUND(AVG(COALESCE(comments, 0)), 2) AS avg_comments
FROM normalized_posts
GROUP BY CASE WHEN is_video = 1 THEN 'video' ELSE 'non_video' END
ORDER BY total_posts DESC;

-- 7) NLP pipeline readiness status (for milestone tracking)
SELECT
    nlp_status,
    COUNT(*) AS total
FROM normalized_posts
GROUP BY nlp_status
ORDER BY total DESC;

-- 8) Candidate posts for NLP (simple filter for text-rich entries)
SELECT
    post_id,
    shortcode,
    datetime_utc,
    caption_word_count,
    location_name,
    nlp_status
FROM normalized_posts
WHERE COALESCE(caption_word_count, 0) >= 15
  AND nlp_status = 'pending'
ORDER BY datetime_utc DESC
LIMIT 25;

-- 9) Example join: posts + hashtag counts per post
SELECT
    p.shortcode,
    p.datetime_utc,
    p.location_name,
    COUNT(h.hashtag) AS hashtag_count,
    p.likes,
    p.comments
FROM normalized_posts p
LEFT JOIN post_hashtags h ON p.post_id = h.post_id
GROUP BY p.post_id, p.shortcode, p.datetime_utc, p.location_name, p.likes, p.comments
ORDER BY hashtag_count DESC, COALESCE(p.likes, 0) DESC
LIMIT 20;

-- 10) Data quality check: missing critical fields
SELECT
    SUM(CASE WHEN shortcode IS NULL OR trim(shortcode) = '' THEN 1 ELSE 0 END) AS missing_shortcode,
    SUM(CASE WHEN datetime_utc IS NULL OR trim(datetime_utc) = '' THEN 1 ELSE 0 END) AS missing_datetime,
    SUM(CASE WHEN caption IS NULL OR trim(caption) = '' THEN 1 ELSE 0 END) AS missing_caption
FROM normalized_posts;
