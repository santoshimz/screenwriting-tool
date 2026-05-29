"""FastAPI routes for screenplay import/export (mount on any app)."""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from draft_store import (
    delete_draft,
    list_draft_summaries,
    list_versions,
    read_draft,
    read_version,
    restore_version_to_draft,
    save_version,
    validate_project_id,
    write_draft,
)
from pdf_export import ExportBody, build_pdf
from screenplay_import import import_pdf_bytes


class DraftSaveBody(BaseModel):
    title: str = ""
    author: str = ""
    editorEntered: bool = False
    beats: list[dict[str, Any]] = Field(default_factory=list)


class VersionSaveBody(DraftSaveBody):
    label: str = Field(default="", max_length=200)


MAX_IMPORT_PDF_BYTES = 35 * 1024 * 1024

router = APIRouter(tags=["screenplay"])


def _require_project_id(project_id: str | None) -> str:
    if not project_id or not str(project_id).strip():
        raise HTTPException(
            status_code=400,
            detail="Missing project_id (query parameter).",
        )
    try:
        return validate_project_id(str(project_id).strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/import-pdf")
async def api_import_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    name = (file.filename or "").lower()
    if not name.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a .pdf file.",
        )
    data = await file.read()
    if len(data) > MAX_IMPORT_PDF_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"PDF too large (max {MAX_IMPORT_PDF_BYTES // (1024 * 1024)} MB).",
        )
    if len(data) < 64:
        raise HTTPException(status_code=400, detail="File is empty or too small.")
    try:
        return import_pdf_bytes(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=f"Could not read this PDF: {exc}",
        ) from exc


@router.get("/api/drafts")
def api_list_drafts() -> dict[str, Any]:
    """List autosaved projects on disk (for home page)."""
    return {"drafts": list_draft_summaries()}


@router.get("/api/draft")
def api_get_draft(project_id: str = Query(..., min_length=8, max_length=64)) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    data = read_draft(pid)
    if data is None:
        raise HTTPException(status_code=404, detail="No draft file for this project.")
    return data


@router.post("/api/draft")
def api_save_draft(
    body: DraftSaveBody,
    project_id: str = Query(..., min_length=8, max_length=64),
) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    return write_draft(pid, body.model_dump())


@router.delete("/api/draft")
def api_delete_draft(project_id: str = Query(..., min_length=8, max_length=64)) -> dict[str, str]:
    pid = _require_project_id(project_id)
    delete_draft(pid)
    return {"ok": "true"}


@router.post("/api/draft/version")
def api_save_named_version(
    body: VersionSaveBody,
    project_id: str = Query(..., min_length=8, max_length=64),
) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    data = body.model_dump()
    label = str(data.pop("label", "") or "")[:200]
    return save_version(pid, data, label=label)


@router.get("/api/draft/versions")
def api_list_named_versions(
    project_id: str = Query(..., min_length=8, max_length=64),
) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    return {"versions": list_versions(pid)}


@router.get("/api/draft/version-read")
def api_read_named_version(
    project_id: str = Query(..., min_length=8, max_length=64),
    version_id: str = Query(..., min_length=16, max_length=16),
) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    data = read_version(pid, version_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Version not found.")
    return data


@router.post("/api/draft/restore-version")
def api_restore_named_version(
    project_id: str = Query(..., min_length=8, max_length=64),
    version_id: str = Query(..., min_length=16, max_length=16),
) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    out = restore_version_to_draft(pid, version_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Version not found.")
    return out


@router.post("/api/export-pdf")
def api_export_pdf(body: ExportBody) -> Response:
    try:
        data = build_pdf(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    safe = re.sub(r"[^\w\s-]", "", body.title or "scriptbox")[:60].strip() or "scriptbox"
    safe = re.sub(r"[-\s]+", "-", safe)
    filename = f"{safe}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
