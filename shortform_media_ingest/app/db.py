import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "places.db")
os.makedirs(DATA_DIR, exist_ok=True)

ENGINE = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)
Base = declarative_base()


class Place(Base):
    __tablename__ = "places"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(512))
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)
    detected_name = Column(String(256), nullable=True)
    category = Column(String(64), nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)


def init_db():
    Base.metadata.create_all(bind=ENGINE)


def get_session():
    return SessionLocal()
