from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any


class VideoData(BaseModel):
    url: HttpUrl
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    transcript: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "url": "https://www.tiktok.com/@example/video/123",
                "caption": "Brunch at Bluebird Cafe",
                "hashtags": ["coffee", "brunch"],
                "transcript": "We stopped by Bluebird Cafe for an amazing latte.",
                "metadata": {"uploader": "@example", "duration_s": 34}
            }
        }
