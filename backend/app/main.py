from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and create all tables on application startup
    init_db()
    yield


app = FastAPI(
    title="Heat Wave Early Warning Backend",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
