from pydantic import BaseModel, HttpUrl
from typing import Optional


class IngestRequest(BaseModel):
    url: HttpUrl
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    transcript: Optional[str] = None


class PlaceOut(BaseModel):
    id: int
    url: HttpUrl
    caption: Optional[str]
    hashtags: Optional[str]
    transcript: Optional[str]
    detected_name: Optional[str]
    category: Optional[str]
    lat: Optional[float]
    lon: Optional[float]

    class Config:
        orm_mode = True
