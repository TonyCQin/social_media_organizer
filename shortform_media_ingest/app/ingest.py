from . import db, classifier


def process_url(session, payload):
    # payload is a pydantic model with url, caption, hashtags, transcript
    meta = payload.dict()
    result = classifier.classify_text(meta.get("caption"), meta.get("hashtags"), meta.get("transcript"))

    place = db.Place(
        url=meta.get("url"),
        caption=meta.get("caption"),
        hashtags=meta.get("hashtags"),
        transcript=meta.get("transcript"),
        detected_name=result.get("detected_name"),
        category=result.get("category"),
        lat=result.get("lat"),
        lon=result.get("lon"),
    )
    session.add(place)
    session.commit()
    session.refresh(place)
    return place
