from fastapi import FastAPI, HTTPException

app = FastAPI(title="VKR API (Legacy ORM)", version="0.0.0")


@app.get("/{path:path}")
def legacy_disabled(path: str):
    raise HTTPException(
        status_code=410,
        detail="Legacy ORM API is frozen. Use services/api/app/main.py as the primary backend.",
    )
