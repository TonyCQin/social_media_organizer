from typing import Dict, Any
import re
from .schema import VideoData


def process_video_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate input and run placeholder NLP processing.

    Returns a dict with detected fields. Replace with real NLP pipeline later.
    """
    # Validate / normalize
    data = VideoData(**payload)

    text_blob = " ".join([t for t in (data.caption or "", " ", data.transcript or "")]).strip()

    entities = extract_entities_from_text(text_blob)
    category, confidence = classify_from_text(text_blob, data.hashtags or [])

    return {
        "url": str(data.url),
        "detected_name": entities.get("place_name"),
        "entities": entities,
        "category": category,
        "confidence": confidence,
        "raw": data.dict(),
    }


def extract_entities_from_text(text: str) -> Dict[str, Any]:
    """Very small heuristic to extract a place-like name and hashtags.

    Look for Title Case sequences as a place name (2-4 words).
    """
    if not text:
        return {"place_name": None}

    matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text)
    place_name = matches[0] if matches else None
    return {"place_name": place_name}


def classify_from_text(text: str, hashtags: list) -> (str, float):
    """Simple heuristic classifier that looks for keywords and hashtags.

    Returns (category, confidence)
    """
    keywords = {
        "coffee": ["coffee", "cafe", "latte", "espresso"],
        "restaurant": ["restaurant", "food", "brunch", "dinner"],
        "park": ["park", "hike", "trail"],
        "beach": ["beach", "surf"],
    }

    text_low = (text or "").lower()
    tag_low = [t.lower().lstrip('#') for t in hashtags]

    for cat, kws in keywords.items():
        for kw in kws:
            if kw in text_low or kw in tag_low:
                return cat, 0.8

    return "unknown", 0.4
