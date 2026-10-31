from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import ingest, judge, notices, profiles, search

app = FastAPI(title="징검")
app.include_router(notices.router)
app.include_router(ingest.router)
app.include_router(search.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router)
app.include_router(judge.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
