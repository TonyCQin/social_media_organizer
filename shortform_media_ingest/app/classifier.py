from typing import Optional
import re


def classify_text(caption: Optional[str], hashtags: Optional[str], transcript: Optional[str]) -> dict:
    text = " ".join([t for t in (caption or "", hashtags or "", transcript or "")])
    text = text.strip()

    # Very small heuristic classifier: look for common place categories
    categories = ["coffee", "restaurant", "park", "museum", "bar", "beach", "hike", "market"]
    found_cat = None
    for c in categories:
        if re.search(r"\b" + re.escape(c) + r"\b", text, flags=re.I):
            found_cat = c
            break

    # Try to detect a place name by looking for Title Case sequences of 2-4 words
    name = None
    matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text)
    if matches:
        name = matches[0]

    # No geocoding here — placeholder None coordinates
    return {
        "detected_name": name,
        "category": found_cat,
        "lat": None,
        "lon": None,
    }
