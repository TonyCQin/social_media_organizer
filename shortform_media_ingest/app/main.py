from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import db, ingest, schemas

app = FastAPI(title="Shortform Media Ingest - Places to Visit")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup_event():
    db.init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=schemas.PlaceOut)
def post_ingest(payload: schemas.IngestRequest):
    session = db.get_session()
    try:
        place = ingest.process_url(session, payload)
        return place
    finally:
        session.close()


@app.get("/locations", response_model=list[schemas.PlaceOut])
def get_locations():
    session = db.get_session()
    try:
        objs = session.query(db.Place).all()
        return objs
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
