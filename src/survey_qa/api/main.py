"""FastAPI application factory.

Run with: uvicorn survey_qa.api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from .routes.qa import router as qa_router

app = FastAPI(
    title="Survey QA API",
    description="Compare a Decipher XML survey against a client questionnaire.",
    version="0.1.0",
)

app.include_router(qa_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
