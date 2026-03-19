import argparse
import csv
import json
import lzma
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


HASHTAG_RE = re.compile(r"#(\w+)")
MENTION_RE = re.compile(r"@([A-Za-z0-9._]+)")


def _safe_get(mapping: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _extract_caption(node: Dict[str, Any]) -> str:
    edges = _safe_get(node, "edge_media_to_caption", "edges", default=[])
    if isinstance(edges, list) and edges:
        first = edges[0]
        if isinstance(first, dict):
            text = _safe_get(first, "node", "text", default="")
            return text if isinstance(text, str) else ""
    return ""


def _extract_tagged_usernames(node: Dict[str, Any]) -> List[str]:
    edges = _safe_get(node, "edge_media_to_tagged_user", "edges", default=[])
    if not isinstance(edges, list):
        return []

    usernames: List[str] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        username = _safe_get(edge, "node", "user", "username")
        if isinstance(username, str) and username:
            usernames.append(username)
    return sorted(set(usernames))


def _extract_hashtags(caption: str) -> List[str]:
    if not caption:
        return []
    return sorted({tag.lower() for tag in HASHTAG_RE.findall(caption)})


def _extract_mentions(caption: str) -> List[str]:
    if not caption:
        return []
    return sorted({mention.lower() for mention in MENTION_RE.findall(caption)})


def _timestamp_to_iso(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _resolve_node(payload: Dict[str, Any]) -> Dict[str, Any]:
    node = payload.get("node")
    if isinstance(node, dict):
        return node
    return payload


def _build_permalink(shortcode: Optional[str]) -> Optional[str]:
    if not shortcode:
        return None
    return f"https://www.instagram.com/p/{shortcode}/"


def parse_instagram_post(payload: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
    node = _resolve_node(payload)

    caption = _extract_caption(node)
    hashtags = _extract_hashtags(caption)
    caption_mentions = _extract_mentions(caption)
    tagged_usernames = _extract_tagged_usernames(node)

    shortcode = node.get("shortcode")
    timestamp = node.get("taken_at_timestamp")
    location = node.get("location") if isinstance(node.get("location"), dict) else None

    sidecar_edges = _safe_get(node, "edge_sidecar_to_children", "edges", default=[])
    sidecar_count = len(sidecar_edges) if isinstance(sidecar_edges, list) else 0

    likes = _safe_get(node, "edge_media_preview_like", "count")
    comments = _safe_get(node, "edge_media_to_comment", "count")

    return {
        "source_file": str(source_file),
        "id": node.get("id"),
        "shortcode": shortcode,
        "permalink": _build_permalink(shortcode),
        "typename": node.get("__typename"),
        "product_type": node.get("product_type"),
        "is_video": bool(node.get("is_video")),
        "timestamp_utc": timestamp,
        "datetime_utc": _timestamp_to_iso(timestamp),
        "caption": caption,
        "caption_word_count": len(caption.split()) if caption else 0,
        "hashtags": hashtags,
        "caption_mentions": caption_mentions,
        "tagged_usernames": tagged_usernames,
        "owner": {
            "id": _safe_get(node, "owner", "id"),
            "username": _safe_get(node, "owner", "username"),
            "full_name": _safe_get(node, "owner", "full_name"),
            "is_verified": _safe_get(node, "owner", "is_verified"),
        },
        "location": {
            "id": location.get("id") if location else None,
            "name": location.get("name") if location else None,
            "slug": location.get("slug") if location else None,
        },
        "engagement": {
            "likes": likes,
            "comments": comments,
            "video_views": node.get("video_view_count") or node.get("video_play_count"),
        },
        "media": {
            "display_url": node.get("display_url"),
            "thumbnail_src": node.get("thumbnail_src"),
            "video_url": node.get("video_url"),
            "video_duration": node.get("video_duration"),
            "sidecar_items": sidecar_count,
        },
        "text_for_nlp": "\n".join(filter(None, [caption, node.get("accessibility_caption") or ""])),
    }


def load_json_file(path: Path) -> Dict[str, Any]:
    if path.suffix == ".xz":
        with lzma.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_input_files(input_path: Path, recursive: bool = True) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return

    pattern = "**/*.json*" if recursive else "*.json*"
    candidates: List[Path] = []
    for candidate in sorted(input_path.glob(pattern)):
        if candidate.suffix == ".json" or candidate.suffixes[-2:] == [".json", ".xz"]:
            candidates.append(candidate)

    preferred_by_base: Dict[str, Path] = {}
    for candidate in candidates:
        if candidate.suffixes[-2:] == [".json", ".xz"]:
            base_name = candidate.name[: -len(".xz")]
        else:
            base_name = candidate.name

        existing = preferred_by_base.get(base_name)
        if existing is None:
            preferred_by_base[base_name] = candidate
            continue

        existing_is_xz = existing.suffixes[-2:] == [".json", ".xz"]
        candidate_is_xz = candidate.suffixes[-2:] == [".json", ".xz"]
        if candidate_is_xz and not existing_is_xz:
            preferred_by_base[base_name] = candidate

    for selected in sorted(preferred_by_base.values()):
        yield selected


def parse_files(input_path: Path, recursive: bool = True, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for file_path in iter_input_files(input_path, recursive=recursive):
        try:
            payload = load_json_file(file_path)
            node_type = _safe_get(payload, "instaloader", "node_type")
            if isinstance(node_type, str) and node_type != "Post":
                continue
            rows.append(parse_instagram_post(payload, file_path))
        except Exception as exc:
            rows.append(
                {
                    "source_file": str(file_path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        if limit is not None and len(rows) >= limit:
            break
    return rows


def write_output(records: List[Dict[str, Any]], output_path: Path, pretty: bool = False) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        if pretty:
            json.dump(records, f, ensure_ascii=False, indent=2)
            f.write("\n")
            return
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def _flatten_for_csv(record: Dict[str, Any]) -> Dict[str, Any]:
    owner = record.get("owner") if isinstance(record.get("owner"), dict) else {}
    location = record.get("location") if isinstance(record.get("location"), dict) else {}
    engagement = record.get("engagement") if isinstance(record.get("engagement"), dict) else {}
    media = record.get("media") if isinstance(record.get("media"), dict) else {}

    return {
        "source_file": record.get("source_file"),
        "id": record.get("id"),
        "shortcode": record.get("shortcode"),
        "permalink": record.get("permalink"),
        "typename": record.get("typename"),
        "product_type": record.get("product_type"),
        "is_video": record.get("is_video"),
        "timestamp_utc": record.get("timestamp_utc"),
        "datetime_utc": record.get("datetime_utc"),
        "caption": record.get("caption"),
        "caption_word_count": record.get("caption_word_count"),
        "hashtags": "|".join(record.get("hashtags", [])) if isinstance(record.get("hashtags"), list) else "",
        "caption_mentions": "|".join(record.get("caption_mentions", [])) if isinstance(record.get("caption_mentions"), list) else "",
        "tagged_usernames": "|".join(record.get("tagged_usernames", [])) if isinstance(record.get("tagged_usernames"), list) else "",
        "owner_id": owner.get("id"),
        "owner_username": owner.get("username"),
        "owner_full_name": owner.get("full_name"),
        "owner_is_verified": owner.get("is_verified"),
        "location_id": location.get("id"),
        "location_name": location.get("name"),
        "location_slug": location.get("slug"),
        "likes": engagement.get("likes"),
        "comments": engagement.get("comments"),
        "video_views": engagement.get("video_views"),
        "display_url": media.get("display_url"),
        "thumbnail_src": media.get("thumbnail_src"),
        "video_url": media.get("video_url"),
        "video_duration": media.get("video_duration"),
        "sidecar_items": media.get("sidecar_items"),
        "text_for_nlp": record.get("text_for_nlp"),
        "error": record.get("error"),
    }


def write_csv_output(records: List[Dict[str, Any]], csv_output_path: Path) -> None:
    csv_output_path.parent.mkdir(parents=True, exist_ok=True)
    flattened_rows = [_flatten_for_csv(record) for record in records]

    fieldnames = [
        "source_file",
        "id",
        "shortcode",
        "permalink",
        "typename",
        "product_type",
        "is_video",
        "timestamp_utc",
        "datetime_utc",
        "caption",
        "caption_word_count",
        "hashtags",
        "caption_mentions",
        "tagged_usernames",
        "owner_id",
        "owner_username",
        "owner_full_name",
        "owner_is_verified",
        "location_id",
        "location_name",
        "location_slug",
        "likes",
        "comments",
        "video_views",
        "display_url",
        "thumbnail_src",
        "video_url",
        "video_duration",
        "sidecar_items",
        "text_for_nlp",
        "error",
    ]

    with csv_output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in flattened_rows:
            writer.writerow(row)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse Instaloader JSON/JSON.XZ files and extract key Instagram post fields.",
    )
    parser.add_argument(
        "--input",
        default="atllovesmo",
        help="File or directory containing Instaloader exports (.json or .json.xz).",
    )
    parser.add_argument(
        "--output",
        default="nlp_processor/examples/instagram_posts.ndjson",
        help="Output path for extracted records.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of files to process.",
    )
    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Only process files in the top-level input directory.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Write output as pretty JSON array instead of NDJSON.",
    )
    parser.add_argument(
        "--csv-output",
        default=None,
        help="Optional CSV output path for flattened records.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    records = parse_files(
        input_path=input_path,
        recursive=not args.non_recursive,
        limit=args.limit,
    )
    write_output(records, output_path=output_path, pretty=args.pretty)

    if args.csv_output:
        csv_output_path = Path(args.csv_output)
        write_csv_output(records, csv_output_path=csv_output_path)

    success_count = sum(1 for r in records if "error" not in r)
    error_count = len(records) - success_count
    if args.csv_output:
        print(
            f"Processed {len(records)} files. Success: {success_count}. Errors: {error_count}. JSON output: {output_path}. CSV output: {args.csv_output}"
        )
    else:
        print(
            f"Processed {len(records)} files. Success: {success_count}. Errors: {error_count}. Output: {output_path}"
        )


if __name__ == "__main__":
    main()
