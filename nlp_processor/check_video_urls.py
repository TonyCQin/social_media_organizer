import argparse
import csv
import sqlite3
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def _try_request(url: str, method: str, timeout: int) -> Tuple[bool, Optional[int], str]:
    req = Request(url, method=method)
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )
    if method == "GET":
        req.add_header("Range", "bytes=0-0")

    try:
        with urlopen(req, timeout=timeout) as response:
            code = getattr(response, "status", None)
            if code is None:
                return True, None, "no_status"
            return 200 <= code < 300, int(code), "ok"
    except HTTPError as exc:
        return False, int(exc.code), f"http_error:{exc.code}"
    except URLError as exc:
        return False, None, f"url_error:{exc.reason}"
    except Exception as exc:
        return False, None, f"error:{exc}"


def check_url_valid(url: str, timeout: int = 5) -> Tuple[bool, Optional[int], str]:
    """
    Check if a URL is accessible (returns 200–299 status code).
    Returns True if valid, False otherwise.
    """
    if not url or not url.strip():
        return False, None, "missing_url"

    ok, code, reason = _try_request(url, method="HEAD", timeout=timeout)
    if ok:
        return True, code, "head_ok"

    if code in {403, 405, 429} or code is None:
        ok_get, code_get, reason_get = _try_request(url, method="GET", timeout=timeout)
        return ok_get, code_get, f"fallback_get:{reason_get}"

    return False, code, reason


def validate_urls_in_db(
    db_path: Path,
    limit: Optional[int] = None,
    delay_sec: float = 0.5,
    timeout: int = 5,
    report_csv: Optional[Path] = None,
) -> Dict[str, int]:
    """
    Check all video_url entries in normalized_posts.
    Update a new url_status column with 'valid' or 'invalid'.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Ensure url_status column exists
        conn.execute(
            """
            ALTER TABLE normalized_posts
            ADD COLUMN url_status TEXT DEFAULT 'unchecked'
            """
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass

    cursor = conn.cursor()
    cursor.execute(
        "SELECT post_id, video_url FROM normalized_posts WHERE video_url IS NOT NULL ORDER BY datetime_utc DESC"
    )
    rows = cursor.fetchall()

    if limit:
        rows = rows[:limit]

    valid_count = 0
    invalid_count = 0
    report_rows = []

    for index, (post_id, video_url) in enumerate(rows, start=1):
        is_valid, status_code, reason = check_url_valid(video_url, timeout=timeout)
        status = "valid" if is_valid else "invalid"
        if status == "valid":
            valid_count += 1
        else:
            invalid_count += 1

        conn.execute(
            "UPDATE normalized_posts SET url_status = ? WHERE post_id = ?",
            (status, post_id),
        )
        conn.commit()

        report_rows.append(
            {
                "post_id": post_id,
                "url_status": status,
                "http_status_code": status_code if status_code is not None else "",
                "reason": reason,
                "video_url": video_url,
            }
        )

        if index % 10 == 0:
            print(f"Checked {index}/{len(rows)}...")

        time.sleep(delay_sec)

    if report_csv:
        report_csv.parent.mkdir(parents=True, exist_ok=True)
        with report_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["post_id", "url_status", "http_status_code", "reason", "video_url"],
            )
            writer.writeheader()
            for row in report_rows:
                writer.writerow(row)

    conn.close()

    return {
        "total_checked": len(rows),
        "valid": valid_count,
        "invalid": invalid_count,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Instagram video URLs and update database status."
    )
    parser.add_argument(
        "--db",
        default="nlp_processor/storage/social_media.db",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of URLs to check.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between checks (seconds) to avoid rate limiting.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--report-csv",
        default="nlp_processor/examples/video_url_validation_report.csv",
        help="Optional CSV report output path.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    db_path = Path(args.db)

    print(f"Validating URLs in {db_path}...")
    report_csv = Path(args.report_csv) if args.report_csv else None
    stats = validate_urls_in_db(
        db_path=db_path,
        limit=args.limit,
        delay_sec=args.delay,
        timeout=args.timeout,
        report_csv=report_csv,
    )

    print(f"\nResults:")
    print(f"  Total checked: {stats['total_checked']}")
    print(f"  Valid: {stats['valid']}")
    print(f"  Invalid: {stats['invalid']}")
    if report_csv:
        print(f"  Report: {report_csv}")


if __name__ == "__main__":
    main()
