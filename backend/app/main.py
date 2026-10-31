from fastapi import FastAPI

from backend.app.routers import ingest, notices, search

app = FastAPI(title="징검")
app.include_router(notices.router)
app.include_router(ingest.router)
app.include_router(search.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
