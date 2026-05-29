"""Persist screenplay drafts per project under ``screenplay/drafts/{project_id}.json``."""
from __future__ import annotations

import json
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
DRAFT_DIR = APP_DIR / "drafts"

# UUID, or legacy stem e.g. ``autosave``
PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9\-]{8,64}$")
# ``secrets.token_hex(8)`` filenames
VERSION_ID_RE = re.compile(r"^[a-f0-9]{16}$")
_VERSION_LABEL_SEQ = re.compile(r"^v(\d+)$", re.IGNORECASE)
MAX_VERSIONS_PER_PROJECT = 50


def validate_project_id(project_id: str) -> str:
    pid = (project_id or "").strip()
    if not PROJECT_ID_RE.fullmatch(pid):
        raise ValueError("Invalid project_id")
    return pid


def draft_path(project_id: str) -> Path:
    return DRAFT_DIR / f"{validate_project_id(project_id)}.json"


def versions_dir(project_id: str) -> Path:
    return DRAFT_DIR / "versions" / validate_project_id(project_id)


def read_draft(project_id: str) -> dict[str, Any] | None:
    path = draft_path(project_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_draft(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    validate_project_id(project_id)
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "title": str(payload.get("title", "")),
        "author": str(payload.get("author", "")),
        "editorEntered": bool(payload.get("editorEntered", False)),
        "beats": payload.get("beats") if isinstance(payload.get("beats"), list) else [],
        "savedAt": datetime.now(timezone.utc).isoformat(),
    }
    draft_path(project_id).write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out


def delete_draft(project_id: str) -> None:
    try:
        pid = validate_project_id(project_id)
    except ValueError:
        return
    try:
        draft_path(pid).unlink(missing_ok=True)
    except OSError:
        pass
    try:
        vd = versions_dir(pid)
        if vd.is_dir():
            shutil.rmtree(vd)
    except OSError:
        pass


def _prune_old_versions(vdir: Path, keep: int) -> None:
    files = sorted(vdir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[keep:]:
        try:
            p.unlink()
        except OSError:
            pass


def _next_default_version_label(project_id: str) -> str:
    """Next label ``v1``, ``v2``, … from max existing ``v`` + number and snapshot count."""
    vdir = versions_dir(validate_project_id(project_id))
    if not vdir.is_dir():
        return "v1"
    max_n = 0
    n_files = 0
    for p in vdir.glob("*.json"):
        if not VERSION_ID_RE.fullmatch(p.stem):
            continue
        n_files += 1
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        m = _VERSION_LABEL_SEQ.match(str(data.get("label") or "").strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    if n_files == 0:
        return "v1"
    return f"v{max(max_n, n_files) + 1}"


def save_version(project_id: str, payload: dict[str, Any], label: str = "") -> dict[str, Any]:
    """Write an explicit named snapshot under ``drafts/versions/{project_id}/``."""
    pid = validate_project_id(project_id)
    vdir = versions_dir(pid)
    vdir.mkdir(parents=True, exist_ok=True)
    version_id = secrets.token_hex(8)
    saved_at = datetime.now(timezone.utc).isoformat()
    lab = (label or "").strip()
    if not lab:
        lab = _next_default_version_label(pid)
    out: dict[str, Any] = {
        "versionId": version_id,
        "savedAt": saved_at,
        "label": lab[:200],
        "title": str(payload.get("title", "")),
        "author": str(payload.get("author", "")),
        "editorEntered": bool(payload.get("editorEntered", False)),
        "beats": payload.get("beats") if isinstance(payload.get("beats"), list) else [],
    }
    (vdir / f"{version_id}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _prune_old_versions(vdir, MAX_VERSIONS_PER_PROJECT)
    return {
        "versionId": version_id,
        "savedAt": saved_at,
        "label": out["label"],
    }


def list_versions(project_id: str) -> list[dict[str, Any]]:
    vdir = versions_dir(validate_project_id(project_id))
    if not vdir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(vdir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        stem = p.stem
        if not VERSION_ID_RE.fullmatch(stem):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            rows.append(
                {
                    "versionId": str(data.get("versionId") or stem),
                    "savedAt": str(data.get("savedAt") or ""),
                    "label": str(data.get("label") or "")[:200],
                    "title": str(data.get("title") or "")[:200],
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return rows


def read_version(project_id: str, version_id: str) -> dict[str, Any] | None:
    vid = (version_id or "").strip().lower()
    if not VERSION_ID_RE.fullmatch(vid):
        return None
    path = versions_dir(validate_project_id(project_id)) / f"{vid}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def restore_version_to_draft(project_id: str, version_id: str) -> dict[str, Any] | None:
    snap = read_version(project_id, version_id)
    if snap is None:
        return None
    return write_draft(
        project_id,
        {
            "title": snap.get("title", ""),
            "author": snap.get("author", ""),
            "beats": snap.get("beats") if isinstance(snap.get("beats"), list) else [],
            "editorEntered": bool(snap.get("editorEntered", False)),
        },
    )


def list_draft_summaries() -> list[dict[str, Any]]:
    if not DRAFT_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in DRAFT_DIR.glob("*.json"):
        stem = p.stem
        if not PROJECT_ID_RE.fullmatch(stem):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out.append(
                    {
                        "project_id": stem,
                        "title": (data.get("title") or "Untitled")[:200],
                        "savedAt": data.get("savedAt") or "",
                    }
                )
        except (OSError, json.JSONDecodeError):
            continue
    out.sort(key=lambda x: str(x.get("savedAt") or ""), reverse=True)
    return out
