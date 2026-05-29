"""Pydantic models and PDF builder for screenplay export."""
from __future__ import annotations

import io
import re
from xml.sax.saxutils import escape

from pydantic import BaseModel, Field
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

ALLOWED_TYPES = frozenset(
    ("scene", "action", "character", "parenthetical", "dialogue", "transition")
)


class Block(BaseModel):
    type: str = Field(..., description="scene|action|character|parenthetical|dialogue|transition")
    text: str = Field(default="")


class ExportBody(BaseModel):
    title: str = Field(default="Untitled", max_length=500)
    author: str = Field(default="", max_length=200)
    blocks: list[Block] = Field(default_factory=list)


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _para_xml(text: str, *, upper: bool = False) -> str:
    """Escape for ReportLab Paragraph mini-HTML; preserve single newlines as <br/>."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for line in t.split("\n"):
        s = line.strip()
        if upper:
            s = s.upper()
        parts.append(escape(s))
    return "<br/>".join(parts) if parts else ""


def build_pdf(body: ExportBody) -> bytes:
    title = _norm_text(body.title) or "Untitled"
    author = _norm_text(body.author)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=1.5 * inch,
        rightMargin=1.0 * inch,
        topMargin=1.0 * inch,
        bottomMargin=1.0 * inch,
        title=title,
    )
    frame_w = letter[0] - doc.leftMargin - doc.rightMargin

    styles = getSampleStyleSheet()
    base = styles["Normal"]
    base.fontName = "Courier"
    base.fontSize = 12
    base.leading = 12

    title_style = ParagraphStyle(
        "ScrTitle",
        parent=base,
        alignment=TA_CENTER,
        fontName="Courier-Bold",
        spaceAfter=0,
        fontSize=14,
        leading=18,
    )
    written_by_style = ParagraphStyle(
        "ScrWrittenBy",
        parent=base,
        alignment=TA_CENTER,
        fontName="Courier",
        fontSize=12,
        leading=14,
        spaceAfter=0,
    )
    author_name_style = ParagraphStyle(
        "ScrAuthorName",
        parent=base,
        alignment=TA_CENTER,
        fontName="Courier",
        fontSize=12,
        leading=14,
        spaceAfter=0,
    )
    scene_style = ParagraphStyle(
        "ScrScene",
        parent=base,
        alignment=TA_LEFT,
        fontName="Courier-Bold",
        spaceBefore=12,
        spaceAfter=6,
    )
    action_style = ParagraphStyle(
        "ScrAction",
        parent=base,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    char_style = ParagraphStyle(
        "ScrChar",
        parent=base,
        alignment=TA_CENTER,
        fontName="Courier-Bold",
        spaceBefore=12,
        spaceAfter=0,
        leftIndent=0,
        rightIndent=0,
    )
    dialogue_indent = 1.0 * inch
    dialogue_width = frame_w - dialogue_indent - 0.5 * inch
    dialogue_style = ParagraphStyle(
        "ScrDialogue",
        parent=base,
        alignment=TA_LEFT,
        leftIndent=dialogue_indent,
        rightIndent=max(0, frame_w - dialogue_indent - dialogue_width),
        spaceAfter=6,
    )
    paren_style = ParagraphStyle(
        "ScrParen",
        parent=base,
        alignment=TA_LEFT,
        leftIndent=dialogue_indent + 0.25 * inch,
        rightIndent=dialogue_style.rightIndent,
        spaceAfter=0,
        spaceBefore=0,
    )
    trans_style = ParagraphStyle(
        "ScrTrans",
        parent=base,
        alignment=TA_RIGHT,
        fontName="Courier-Bold",
        spaceBefore=12,
        spaceAfter=12,
    )

    # Title page: vertically centered block — Title, Written By, Author (page 1 only).
    inner_h = letter[1] - doc.topMargin - doc.bottomMargin
    title_page_est = (
        title_style.leading * max(1, (len(title) + 50) // 52)
        + 0.45 * inch
        + written_by_style.leading
        + 0.18 * inch
        + author_name_style.leading
    )
    top_spacer = max(36, (inner_h - title_page_est) / 2)

    story: list = []
    story.append(Spacer(1, top_spacer))
    story.append(Paragraph(escape(title), title_style))
    story.append(Spacer(1, 0.45 * inch))
    story.append(Paragraph(escape("Written By"), written_by_style))
    story.append(Spacer(1, 0.18 * inch))
    story.append(
        Paragraph(escape(author) if author else "\u00a0", author_name_style),
    )

    beat_flowables: list = []
    for block in body.blocks:
        btype = (block.type or "").strip().lower()
        if btype not in ALLOWED_TYPES:
            raise ValueError(f"Unknown block type: {block.type}")
        raw = block.text or ""
        if not raw.strip():
            continue
        xml = _para_xml(raw)

        if btype == "scene":
            beat_flowables.append(Paragraph(_para_xml(raw, upper=True), scene_style))
        elif btype == "action":
            beat_flowables.append(Paragraph(xml, action_style))
        elif btype == "character":
            beat_flowables.append(Paragraph(_para_xml(raw, upper=True), char_style))
        elif btype == "parenthetical":
            flat = " ".join(
                ln.strip() for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip()
            )
            inner = f"({escape(flat)})" if flat else ""
            beat_flowables.append(Paragraph(inner, paren_style))
        elif btype == "dialogue":
            beat_flowables.append(Paragraph(xml, dialogue_style))
        elif btype == "transition":
            beat_flowables.append(Paragraph(_para_xml(raw, upper=True), trans_style))

    if beat_flowables:
        story.append(PageBreak())
        story.extend(beat_flowables)

    doc.build(story)
    return buf.getvalue()
