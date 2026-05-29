"""Extract screenplay structure from PDF bytes → editor payload (title, author, beats)."""
from __future__ import annotations

import io
import re
from typing import Any

from pypdf import PdfReader

SCENE_RE = re.compile(
    r"^(INT\.|EXT\.|INT\./EXT\.|INT\s*/\s*EXT\.|I/E\.)\s",
    re.IGNORECASE,
)

# Typical US screenplay PDF columns (points from left); tuned on ScriptSlug-style PDFs.
X_ACTION_MAX = 145.0
X_DIALOGUE_MAX = 205.0
X_PAREN_MAX = 232.0
X_CHARACTER_MIN = 218.0
X_PAGE_NUM_MIN = 480.0


def looks_like_transition(line: str) -> bool:
    u = line.upper().strip()
    if u.startswith(">"):
        return True
    if u.endswith("TO:"):
        return True
    if u in {"FADE IN:", "FADE OUT.", "FADE OUT:", "THE END.", "THE END"}:
        return True
    return False


def looks_like_character(line: str) -> bool:
    line = line.replace("\u2019", "'").strip()
    if len(line) > 48:
        return False
    if SCENE_RE.match(line):
        return False
    if line.startswith("("):
        return False
    if line.endswith(":"):
        return False
    if line.endswith("!") or line.endswith("?"):
        return False
    if line.endswith(".") and "(" not in line:
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 2:
        return False
    if any(c.islower() for c in line):
        return False
    if len(line) > 22 and " " not in line:
        return False
    if len(line.split()) > 6:
        return False
    return True


def _visitor_chunks(page: Any) -> list[tuple[float, float, str]]:
    chunks: list[tuple[float, float, str]] = []

    def visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
        if not text or not str(text).strip():
            return
        x = float(tm[4])
        y = float(tm[5])
        chunks.append((x, y, str(text)))

    try:
        page.extract_text(visitor_text=visitor)
    except Exception:
        return []
    return chunks


def _cluster_lines(
    chunks: list[tuple[float, float, str]], y_tol: float = 5.0
) -> list[tuple[float, float, str, str]]:
    """One row per visual line: (min_x, max_x, avg_y, merged_text).

    Many screenplay PDFs place the scene slug near the *bottom* of the text block on
    each page (low y) and dialogue higher up. Reading order is bottom-to-top in y,
    i.e. ascending y — not descending.
    """
    if not chunks:
        return []
    chunks = sorted(chunks, key=lambda c: (c[1], c[0]))
    rows: list[list[tuple[float, float, str]]] = []
    row: list[tuple[float, float, str]] = [chunks[0]]
    base_y = chunks[0][1]
    for c in chunks[1:]:
        if abs(c[1] - base_y) <= y_tol:
            row.append(c)
        else:
            rows.append(row)
            row = [c]
            base_y = c[1]
    rows.append(row)

    out: list[tuple[float, float, str, str]] = []
    for parts in rows:
        parts.sort(key=lambda p: p[0])
        min_x = min(p[0] for p in parts)
        max_x = max(p[0] for p in parts)
        avg_y = sum(p[1] for p in parts) / len(parts)
        text = "".join(p[2] for p in parts)
        out.append((min_x, max_x, avg_y, text))
    return out


def _all_caps_superimpose_or_title(t: str) -> bool:
    """Long ALL-CAPS lines are usually superimpose / chyron / title card, not dialogue."""
    t = t.strip()
    if len(t) < 18:
        return False
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 12:
        return False
    return not any(c.islower() for c in t)


def _classify_row(min_x: float, text: str) -> str:
    t = text.strip()
    if not t:
        return "skip"
    if min_x >= X_PAGE_NUM_MIN and re.fullmatch(r"\d+\.?", t):
        return "skip"
    if SCENE_RE.match(t):
        return "scene"
    if looks_like_transition(t):
        return "transition"
    if _all_caps_superimpose_or_title(t):
        return "action"
    # Parentheticals sit between dialogue and character columns
    if t.startswith("(") and min_x >= X_DIALOGUE_MAX - 10:
        return "parenthetical"
    if min_x >= X_CHARACTER_MIN and looks_like_character(t):
        return "character"
    if X_DIALOGUE_MAX <= min_x < X_CHARACTER_MIN and not t.startswith("("):
        # Rare stray; treat as dialogue if it looks like speech
        if any(c.islower() for c in t) or len(t) > 30:
            return "dialogue"
    if min_x >= X_CHARACTER_MIN:
        # Long line in character column → treat as action (misplaced)
        return "action"
    if X_ACTION_MAX <= min_x < X_DIALOGUE_MAX:
        return "dialogue"
    return "action"


def extract_geometric_events(reader: PdfReader, skip_first_pages: int = 1) -> list[tuple[str, str]]:
    """Ordered (kind, text) using x/y positions (best for studio screenplay PDFs)."""
    events: list[tuple[str, str]] = []
    for idx, page in enumerate(reader.pages):
        if idx < skip_first_pages:
            continue
        chunks = _visitor_chunks(page)
        for min_x, _max_x, _y, text in _cluster_lines(chunks):
            kind = _classify_row(min_x, text)
            if kind == "skip":
                continue
            t = " ".join(text.split())
            if not t:
                continue
            events.append((kind, t))
    return events


def _merge_events(events: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Merge consecutive action / dialogue; keep scene, character, parenthetical, transition separate."""
    blocks: list[dict[str, str]] = []

    def flush_action(buf: list[str]) -> None:
        if buf:
            blocks.append({"type": "action", "text": "\n\n".join(buf)})

    def flush_dialogue(buf: list[str]) -> None:
        if buf:
            blocks.append({"type": "dialogue", "text": "\n".join(buf)})

    i = 0
    n = len(events)
    while i < n:
        kind, text = events[i]
        if kind == "scene":
            blocks.append({"type": "scene", "text": text})
            i += 1
            continue
        if kind == "transition":
            blocks.append({"type": "transition", "text": text})
            i += 1
            continue
        if kind == "character":
            blocks.append({"type": "character", "text": text})
            i += 1
            if i < n and events[i][0] == "parenthetical":
                ptxt = events[i][1].strip()
                if ptxt.startswith("(") and ptxt.endswith(")"):
                    ptxt = ptxt[1:-1].strip()
                blocks.append({"type": "parenthetical", "text": ptxt})
                i += 1
            dial: list[str] = []
            while i < n and events[i][0] == "dialogue":
                dial.append(events[i][1])
                i += 1
            flush_dialogue(dial)
            continue
        if kind == "parenthetical":
            ptxt = text.strip()
            if ptxt.startswith("(") and ptxt.endswith(")"):
                ptxt = ptxt[1:-1].strip()
            blocks.append({"type": "parenthetical", "text": ptxt})
            i += 1
            continue
        if kind == "action":
            abuf: list[str] = [text]
            i += 1
            while i < n and events[i][0] == "action":
                abuf.append(events[i][1])
                i += 1
            flush_action(abuf)
            continue
        if kind == "dialogue":
            dbuf: list[str] = [text]
            i += 1
            while i < n and events[i][0] == "dialogue":
                dbuf.append(events[i][1])
                i += 1
            flush_dialogue(dbuf)
            continue
        i += 1

    return blocks


def trim_events_to_script(events: list[tuple[str, str]]) -> list[tuple[str, str]]:
    for i, (k, t) in enumerate(events):
        if k == "scene" and SCENE_RE.match(t.strip()):
            return events[i:]
        if k == "action" and t.strip().upper().startswith("TITLES"):
            return events[i:]
    return events


def extract_lines(reader: PdfReader) -> list[str]:
    """Legacy: layout text lines (fallback)."""
    lines: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text(extraction_mode="layout")
        except TypeError:
            t = page.extract_text()
        if not t:
            continue
        for raw in t.split("\n"):
            s = raw.strip()
            if not s:
                continue
            if re.fullmatch(r"\d+\.?", s):
                continue
            if re.fullmatch(r"\d+\s*of\s*\d+", s, re.I):
                continue
            lines.append(s)
    return lines


def trim_to_script_start(lines: list[str]) -> list[str]:
    for i, ln in enumerate(lines):
        if SCENE_RE.match(ln):
            return lines[i:]
        if ln.upper().startswith("TITLES"):
            return lines[i:]
    return lines


def parse_lines(lines: list[str]) -> list[dict[str, str]]:
    lines = trim_to_script_start(lines)
    blocks: list[dict[str, str]] = []
    i = 0
    n = len(lines)

    def emit(kind: str, text: str) -> None:
        t = text.strip()
        if t:
            blocks.append({"type": kind, "text": t})

    while i < n:
        line = lines[i]
        if SCENE_RE.match(line):
            emit("scene", line)
            i += 1
            continue
        if looks_like_transition(line):
            emit("transition", line)
            i += 1
            continue
        if looks_like_character(line):
            emit("character", line)
            i += 1
            if i < n and lines[i].lstrip().startswith("("):
                raw_p = lines[i].strip()
                i += 1
                inner = (
                    raw_p[1:-1].strip()
                    if raw_p.startswith("(") and raw_p.endswith(")")
                    else raw_p
                )
                emit("parenthetical", inner)
            dialogue_chunk: list[str] = []
            while i < n:
                nxt = lines[i]
                if SCENE_RE.match(nxt) or looks_like_transition(nxt):
                    break
                if looks_like_character(nxt):
                    break
                dialogue_chunk.append(nxt)
                i += 1
            if dialogue_chunk:
                emit("dialogue", "\n".join(dialogue_chunk))
            continue

        action_chunk: list[str] = []
        while i < n:
            nxt = lines[i]
            if SCENE_RE.match(nxt) or looks_like_transition(nxt):
                break
            if looks_like_character(nxt):
                break
            action_chunk.append(nxt)
            i += 1
        if action_chunk:
            emit("action", "\n\n".join(action_chunk))

    return blocks


def blocks_to_beats(blocks: list[dict[str, str]]) -> list[dict[str, str]]:
    order = ("scene", "action", "character", "parenthetical", "dialogue", "transition")
    beats: list[dict[str, str]] = []
    for b in blocks:
        beat = {k: "" for k in order}
        t = b.get("type", "action")
        if t in beat:
            beat[t] = b.get("text", "")
        else:
            beat["action"] = b.get("text", "")
        beats.append(beat)
    return beats


def guess_title_author(reader: PdfReader) -> tuple[str, str]:
    try:
        t = reader.pages[0].extract_text() or ""
    except Exception:
        return "Untitled", ""
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    title = lines[0] if lines else "Untitled"
    author = ""
    for j, ln in enumerate(lines):
        if re.match(r"^written by$", ln, re.I) and j + 1 < len(lines):
            author = lines[j + 1]
            break
    return title[:500], author[:200]


def import_pdf_bytes(pdf_bytes: bytes) -> dict[str, Any]:
    """Parse PDF bytes into ``{title, author, beats}`` for the web editor."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    title, author = guess_title_author(reader)

    events = extract_geometric_events(reader)
    events = trim_events_to_script(events)

    if len(events) >= 50:
        blocks = _merge_events(events)
    else:
        lines = extract_lines(reader)
        blocks = parse_lines(lines)

    beats = blocks_to_beats(blocks)
    return {"title": title, "author": author, "beats": beats}
