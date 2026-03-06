from fastapi import FastAPI

app = FastAPI(title="MediaHub API Gateway", version="0.1.0")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "api", "status": "ok", "message": "MediaHub API bootstrap"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
