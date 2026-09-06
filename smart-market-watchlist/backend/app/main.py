from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routes.watchlist import router as watchlist_router

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Market Watchlist", version="0.1.0")

# CORS — allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(watchlist_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
