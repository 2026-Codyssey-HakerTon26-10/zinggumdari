from fastapi import FastAPI

from backend.app.routers import notices

app = FastAPI(title="징검")
app.include_router(notices.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
