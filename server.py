#!/usr/bin/env python3
"""ScriptBox editor: static UI + PDF import/export API."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from screenplay_routes import router as screenplay_router

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="ScriptBox")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTML routes first so they are never shadowed by the API router or static mount.
@app.get("/")
def index() -> FileResponse:
    path = STATIC_DIR / "index.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="index.html missing")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/index.html")
def index_html_redirect() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=307)


@app.get("/edit")
def screenplay_edit() -> FileResponse:
    path = STATIC_DIR / "edit.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="edit.html missing")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/edit.html")
def screenplay_edit_html_redirect(request: Request) -> RedirectResponse:
    q = request.url.query
    loc = f"/edit?{q}" if q else "/edit"
    return RedirectResponse(url=loc, status_code=307)


app.include_router(screenplay_router)
# Same routes under /screenplay/api/* so Import works when the UI is opened at /screenplay/ (e.g. main webapp).
app.include_router(screenplay_router, prefix="/screenplay")


app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=True)
