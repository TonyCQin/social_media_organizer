import argparse
import sqlite3
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Optional

# Try to import whisper, provide installation instructions if missing
try:
    import whisper
except ImportError:
    print(
        "ERROR: 'openai-whisper' not installed.\n"
        "Install with: pip install openai-whisper\n"
        "Note: Requires ffmpeg on system PATH for audio extraction."
    )
    sys.exit(1)


def _timestamp_prefix_from_filename(mp4_filename: str) -> Optional[str]:
    stem = Path(mp4_filename).stem
    marker = "_UTC"
    marker_index = stem.find(marker)
    if marker_index == -1:
        return None
    return stem[: marker_index + len(marker)]


def find_post_id_by_timestamp(conn: sqlite3.Connection, mp4_filename: str) -> Optional[str]:
    """
    Match MP4 filename (YYYY-MM-DD_HH-MM-SS_UTC[_N].mp4) to post_id
    by finding the normalized_posts record with matching datetime_utc.
    Returns post_id or None if no match found.
    """
    try:
        prefix = _timestamp_prefix_from_filename(mp4_filename)
        if not prefix:
            return None

        cursor = conn.cursor()
        cursor.execute(
            "SELECT post_id FROM normalized_posts WHERE source_file LIKE ? ORDER BY datetime_utc DESC LIMIT 1",
            (f"%{prefix}%",),
        )
        result = cursor.fetchone()
        if result:
            return result[0]

        fallback = prefix.replace("_UTC", "")
        date_part, time_part = fallback.rsplit("_", 1)
        iso_datetime = f"{date_part}T{time_part.replace('-', ':')}"
        cursor.execute(
            "SELECT post_id FROM normalized_posts WHERE datetime_utc LIKE ? ORDER BY datetime_utc DESC LIMIT 1",
            (f"{iso_datetime}%",),
        )
        fallback_result = cursor.fetchone()
        return fallback_result[0] if fallback_result else None
    except Exception as e:
        print(f"  Warning: Could not map {mp4_filename}: {e}")
        return None


def transcribe_mp4(
    model: "whisper.Whisper",
    mp4_path: Path,
    language: str = "en",
) -> Optional[Dict]:
    """
    Transcribe an MP4 using Whisper.
    Returns dict with 'text' (transcript), 'confidence' (average probability).
    Returns None on error.
    """
    try:
        print(f"  Transcribing {mp4_path.name}...", end=" ", flush=True)
        result = model.transcribe(str(mp4_path), language=language)
        print(f"✓")

        transcript_text = result.get("text", "").strip()

        # Calculate average confidence from segment-level probabilities
        segments = result.get("segments", [])
        if segments and any("no_speech_prob" in seg for seg in segments):
            confidences = [1.0 - seg.get("no_speech_prob", 0.0) for seg in segments]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        else:
            # Whisper doesn't always provide confidence; default to reasonable estimate
            avg_confidence = 0.85

        return {
            "text": transcript_text,
            "confidence": round(avg_confidence, 4),
            "language": language,
        }
    except Exception as e:
        print(f"✗ ({e})")
        return None


def store_transcript(
    conn: sqlite3.Connection,
    post_id: str,
    video_url: str,
    transcript: str,
    confidence: float,
    model_version: str = "whisper-base",
) -> bool:
    """
    Insert or update video_transcripts record. Return True on success.
    """
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO video_transcripts
            (post_id, video_url, transcript, confidence, model_version, processed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                video_url,
                transcript,
                confidence,
                model_version,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.execute(
            "UPDATE normalized_posts SET nlp_status = 'transcribed' WHERE post_id = ?",
            (post_id,),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"    Error storing transcript: {e}")
        return False


def process_mp4_directory(
    mp4_dir: Path,
    db_path: Path,
    model_name: str = "base",
    language: str = "en",
    limit: Optional[int] = None,
    output_dir: Optional[Path] = Path("nlp_processor/examples/transcripts"),
) -> Dict[str, int]:
    """
    Scan MP4 directory, match to posts, transcribe, and store results.
    """
    mp4_files = sorted(mp4_dir.glob("*.mp4"))

    if limit:
        mp4_files = mp4_files[:limit]

    print(f"Loading Whisper model '{model_name}' once for batch...", end=" ", flush=True)
    model = whisper.load_model(model_name)
    print("✓")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "total_found": len(mp4_files),
        "matched": 0,
        "transcribed": 0,
        "skipped": 0,
        "errors": 0,
    }

    for idx, mp4_path in enumerate(mp4_files, start=1):
        print(f"\n[{idx}/{len(mp4_files)}] {mp4_path.name}")

        # Match MP4 to post_id
        post_id = find_post_id_by_timestamp(conn, mp4_path.name)
        if not post_id:
            print(f"  No matching post found in database. Skipping.")
            stats["skipped"] += 1
            continue

        stats["matched"] += 1

        # Check if already transcribed
        cursor = conn.cursor()
        cursor.execute("SELECT transcript FROM video_transcripts WHERE post_id = ?", (post_id,))
        if cursor.fetchone():
            print(f"  Already transcribed. Skipping.")
            stats["skipped"] += 1
            continue

        # Get video_url for record-keeping
        cursor.execute("SELECT video_url FROM normalized_posts WHERE post_id = ?", (post_id,))
        url_result = cursor.fetchone()
        video_url = url_result[0] if url_result else ""

        # Transcribe
        result = transcribe_mp4(model=model, mp4_path=mp4_path, language=language)
        if result:
            if store_transcript(
                conn=conn,
                post_id=post_id,
                video_url=video_url,
                transcript=result["text"],
                confidence=result["confidence"],
                model_version=f"whisper-{model_name}",
            ):
                stats["transcribed"] += 1
                if output_dir:
                    transcript_file = output_dir / f"{post_id}.txt"
                    transcript_file.write_text(result["text"], encoding="utf-8")
                print(f"    Stored ({len(result['text'].split())} words, confidence={result['confidence']:.3f})")
            else:
                stats["errors"] += 1
        else:
            stats["errors"] += 1

    conn.close()
    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcribe local MP4 files using Whisper and store in database."
    )
    parser.add_argument(
        "--mp4-dir",
        default="atllovesmo",
        help="Directory containing MP4 files.",
    )
    parser.add_argument(
        "--db",
        default="nlp_processor/storage/social_media.db",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (tiny=39MB, base=140MB, small=466MB, etc.).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of MP4s to transcribe (for testing).",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language hint for Whisper transcription.",
    )
    parser.add_argument(
        "--output-dir",
        default="nlp_processor/examples/transcripts",
        help="Optional folder to write transcript .txt files by post_id.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    mp4_dir = Path(args.mp4_dir)
    db_path = Path(args.db)

    if not mp4_dir.exists():
        print(f"ERROR: Directory {mp4_dir} not found.")
        sys.exit(1)

    if not db_path.exists():
        print(f"ERROR: Database {db_path} not found.")
        sys.exit(1)

    print(f"Processing MP4s from: {mp4_dir}")
    print(f"Database: {db_path}")
    print(f"Whisper model: {args.model}")
    if args.limit:
        print(f"Limit: {args.limit} files")

    stats = process_mp4_directory(
        mp4_dir=mp4_dir,
        db_path=db_path,
        model_name=args.model,
        language=args.language,
        limit=args.limit,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )

    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  Total MP4s found: {stats['total_found']}")
    print(f"  Matched to posts: {stats['matched']}")
    print(f"  Successfully transcribed: {stats['transcribed']}")
    print(f"  Skipped (already processed): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
