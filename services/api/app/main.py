from fastapi import FastAPI

from app.db import Base, engine
from app.dependencies import pipeline_service
from app.routes import api_router

app = FastAPI(title="MediaHub API", version="0.2.0")
app.include_router(api_router)


@app.on_event("startup")
def startup() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS mediahub")
    Base.metadata.create_all(bind=engine)
    pipeline_service.startup()


@app.on_event("shutdown")
def shutdown() -> None:
    pipeline_service.shutdown()
