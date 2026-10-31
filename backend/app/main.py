from fastapi import FastAPI

app = FastAPI(title="징검")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
