"""Pydantic models and PDF builder for screenplay export (Final Draft / A4 layout)."""
from __future__ import annotations

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, Field
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

ALLOWED_TYPES = frozenset(
    ("scene", "action", "character", "parenthetical", "dialogue", "transition")
)

# Measured from Final Draft / Kanya Raasi A4 reference PDF.
PAGE_SIZE = A4
LEFT_MARGIN = 1.5 * inch
RIGHT_MARGIN = 1.0 * inch
TOP_MARGIN = 1.0 * inch
BOTTOM_MARGIN = 1.0 * inch
SCENE_NUM_LEFT = 0.75 * inch
ACTION_LEFT = 1.5 * inch
DIALOGUE_LEFT = 2.5 * inch
CHARACTER_LEFT = 3.5 * inch
PAREN_LEFT = 2.902 * inch
PAGE_NUM_RIGHT_INSET = 0.73 * inch
SCENE_BREAK_SPACE = 24  # space before new scene (36pt from prev line incl. 12pt leading)
SCENE_TO_ACTION_SPACE = 12  # 24pt baseline gap after scene heading line
ACTION_SPACE_BEFORE = 12  # blank line above action after dialogue / speech blocks

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_REG = "CourierPrime"
FONT_BOLD = "CourierPrime-Bold"
_FONT_REGISTERED = False


def _ensure_fonts() -> None:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    reg = FONT_DIR / "CourierPrime-Regular.ttf"
    bold = FONT_DIR / "CourierPrime-Bold.ttf"
    if reg.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont(FONT_REG, str(reg)))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
        pdfmetrics.registerFontFamily(
            FONT_REG,
            normal=FONT_REG,
            bold=FONT_BOLD,
            italic=FONT_REG,
            boldItalic=FONT_BOLD,
        )
    else:
        FONT_REG_FALLBACK = "Courier"
        FONT_BOLD_FALLBACK = "Courier-Bold"
        globals()["FONT_REG"] = FONT_REG_FALLBACK
        globals()["FONT_BOLD"] = FONT_BOLD_FALLBACK
    _FONT_REGISTERED = True


class Block(BaseModel):
    type: str = Field(..., description="scene|action|character|parenthetical|dialogue|transition")
    text: str = Field(default="")


class ExportBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(default="Untitled", max_length=500)
    author: str = Field(default="", max_length=200)
    script_type: str = Field(default="", max_length=120, alias="scriptType")
    working_title_note: str = Field(default="", max_length=120, alias="workingTitleNote")
    contact_email: str = Field(default="", max_length=200, alias="contactEmail")
    copyright_line: str = Field(default="", max_length=300, alias="copyrightLine")
    production_company: str = Field(default="", max_length=300, alias="productionCompany")
    blocks: list[Block] = Field(default_factory=list)


class ScreenplayDocTemplate(SimpleDocTemplate):
    """Tracks where numbered script pages begin (after title page)."""

    script_start_page: int | None = None
    title_meta: dict[str, str | list[str]] = {}


class SceneHeadingFlowable(Flowable):
    """Scene number at 0.75\" + heading at 1.5\" on one line."""

    def __init__(self, number: int, text: str) -> None:
        super().__init__()
        self.number = number
        self.text = (text or "").strip().upper()
        self.height = 12

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        return availWidth, self.height

    def draw(self) -> None:
        c = self.canv
        c.setFont(FONT_BOLD, 12)
        c.drawString(SCENE_NUM_LEFT - LEFT_MARGIN, 0, str(self.number))
        c.drawString(0, 0, self.text)


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _para_xml(text: str, *, upper: bool = False) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for line in t.split("\n"):
        s = line.strip()
        if upper:
            s = s.upper()
        parts.append(escape(s))
    return "<br/>".join(parts) if parts else ""


def _styles(frame_w: float) -> dict[str, ParagraphStyle]:
    base_kw = dict(fontName=FONT_REG, fontSize=12, leading=12)
    dialogue_width = frame_w - (DIALOGUE_LEFT - LEFT_MARGIN) - 0.5 * inch
    return {
        "title": ParagraphStyle(
            "ScrTitle",
            fontName=FONT_BOLD,
            fontSize=12,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "banner": ParagraphStyle(
            "ScrBanner",
            fontName=FONT_REG,
            fontSize=12,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "written_by": ParagraphStyle(
            "ScrWrittenBy",
            fontName=FONT_REG,
            fontSize=12,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "author": ParagraphStyle(
            "ScrAuthor",
            fontName=FONT_REG,
            fontSize=12,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "footer": ParagraphStyle(
            "ScrFooter",
            fontName=FONT_REG,
            fontSize=12,
            leading=12,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "action": ParagraphStyle(
            "ScrAction",
            fontName=FONT_REG,
            fontSize=12,
            leading=12,
            alignment=TA_LEFT,
            leftIndent=0,
            spaceBefore=0,
            spaceAfter=0,
        ),
        "action_spaced": ParagraphStyle(
            "ScrActionSpaced",
            fontName=FONT_REG,
            fontSize=12,
            leading=12,
            alignment=TA_LEFT,
            leftIndent=0,
            spaceBefore=ACTION_SPACE_BEFORE,
            spaceAfter=0,
        ),
        "character": ParagraphStyle(
            "ScrChar",
            fontName=FONT_BOLD,
            fontSize=12,
            leading=12,
            alignment=TA_LEFT,
            leftIndent=CHARACTER_LEFT - LEFT_MARGIN,
            spaceBefore=12,
            spaceAfter=0,
            keepWithNext=True,
        ),
        "dialogue": ParagraphStyle(
            "ScrDialogue",
            fontName=FONT_REG,
            fontSize=12,
            leading=12,
            alignment=TA_LEFT,
            leftIndent=DIALOGUE_LEFT - LEFT_MARGIN,
            rightIndent=max(0, frame_w - (DIALOGUE_LEFT - LEFT_MARGIN) - dialogue_width),
            spaceAfter=0,
        ),
        "parenthetical": ParagraphStyle(
            "ScrParen",
            fontName=FONT_REG,
            fontSize=12,
            leading=12,
            alignment=TA_LEFT,
            leftIndent=PAREN_LEFT - LEFT_MARGIN,
            rightIndent=max(0, frame_w - (DIALOGUE_LEFT - LEFT_MARGIN) - dialogue_width),
            spaceAfter=0,
            spaceBefore=0,
            keepWithNext=True,
        ),
        "transition": ParagraphStyle(
            "ScrTrans",
            fontName=FONT_BOLD,
            fontSize=12,
            leading=12,
            alignment=TA_RIGHT,
            spaceBefore=12,
            spaceAfter=24,
        ),
        "scene_break": ParagraphStyle(
            "ScrSceneBreak",
            fontName=FONT_REG,
            fontSize=1,
            leading=1,
            spaceBefore=SCENE_BREAK_SPACE,
            spaceAfter=0,
        ),
    }


def _action_style(st: dict[str, ParagraphStyle], prev_type: str | None) -> ParagraphStyle:
    """Blank line above action except when the previous block already added vertical gap."""
    if prev_type in (None, "scene", "transition"):
        return st["action"]
    return st["action_spaced"]


def _parenthetical_flowable(raw: str, st: dict[str, ParagraphStyle]) -> Paragraph:
    flat = " ".join(ln.strip() for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip())
    inner = flat.strip("()")
    paren = f"({escape(inner)})" if inner else ""
    return Paragraph(paren, st["parenthetical"])


def _following_scene_content(
    blocks: list[Block],
    start: int,
    *,
    st: dict[str, ParagraphStyle],
) -> tuple[list, int]:
    """First non-empty block(s) after a scene heading (kept on the same page)."""
    j = start
    while j < len(blocks):
        block = blocks[j]
        ntype = (block.type or "").strip().lower()
        raw = block.text or ""
        if not raw.strip():
            j += 1
            continue
        if ntype == "scene":
            break
        if ntype == "action":
            return [Paragraph(_para_xml(raw), st["action"])], j + 1
        if ntype == "character":
            return _character_speech_group(blocks, j, st=st)
        if ntype == "parenthetical":
            return [_parenthetical_flowable(raw, st)], j + 1
        if ntype == "dialogue":
            return [Paragraph(_para_xml(raw), st["dialogue"])], j + 1
        if ntype == "transition":
            return [Paragraph(_para_xml(raw, upper=True), st["transition"])], j + 1
        break
    return [], j


def _scene_opening_group(
    blocks: list[Block],
    start: int,
    *,
    scene_num: int,
    prev_type: str | None,
    st: dict[str, ParagraphStyle],
) -> tuple[list, int, int]:
    """Scene heading + spacer + opening content; avoids orphan slug lines at page bottom."""
    block = blocks[start]
    raw = block.text or ""
    scene_num += 1
    group: list = []
    if scene_num > 1 and prev_type != "transition":
        group.append(Paragraph("\u00a0", st["scene_break"]))
    group.append(SceneHeadingFlowable(scene_num, raw))
    group.append(Spacer(1, SCENE_TO_ACTION_SPACE))
    follow, j = _following_scene_content(blocks, start + 1, st=st)
    group.extend(follow)
    return group, j, scene_num


def _append_block_flowables(
    beat_flowables: list,
    block: Block,
    *,
    st: dict[str, ParagraphStyle],
    prev_type: str | None,
    scene_num: int,
) -> tuple[int, str]:
    """Append PDF flowables for one block; returns updated scene_num and prev_type."""
    btype = (block.type or "").strip().lower()
    raw = block.text or ""
    xml = _para_xml(raw)

    if btype == "scene":
        raise ValueError("scene blocks must use _scene_opening_group")
    elif btype == "action":
        beat_flowables.append(Paragraph(xml, _action_style(st, prev_type)))
    elif btype == "character":
        beat_flowables.append(Paragraph(_para_xml(raw, upper=True), st["character"]))
    elif btype == "parenthetical":
        beat_flowables.append(_parenthetical_flowable(raw, st))
    elif btype == "dialogue":
        beat_flowables.append(Paragraph(xml, st["dialogue"]))
    elif btype == "transition":
        beat_flowables.append(Paragraph(_para_xml(raw, upper=True), st["transition"]))

    return scene_num, btype


def _character_speech_group(
    blocks: list[Block],
    start: int,
    *,
    st: dict[str, ParagraphStyle],
) -> tuple[list, int]:
    """Character + optional parenthetical(s) + dialogue kept on the same page."""
    group: list = []
    j = start
    block = blocks[j]
    raw = block.text or ""
    group.append(Paragraph(_para_xml(raw, upper=True), st["character"]))
    j += 1
    while j < len(blocks):
        ntype = (blocks[j].type or "").strip().lower()
        if ntype == "parenthetical":
            group.append(_parenthetical_flowable(blocks[j].text or "", st))
            j += 1
        elif ntype == "dialogue":
            text = blocks[j].text or ""
            if not text.strip():
                break
            group.append(Paragraph(_para_xml(text), st["dialogue"]))
            j += 1
        else:
            break
    return group, j


def _draw_page_number(canvas, doc: ScreenplayDocTemplate) -> None:
    if doc.script_start_page is None:
        return
    page = canvas.getPageNumber()
    if page < doc.script_start_page:
        return
    num = page - doc.script_start_page + 1
    canvas.saveState()
    canvas.setFont(FONT_REG, 12)
    canvas.drawRightString(
        PAGE_SIZE[0] - PAGE_NUM_RIGHT_INSET,
        PAGE_SIZE[1] - TOP_MARGIN - 12,
        str(num),
    )
    canvas.restoreState()


def _draw_title_page(canvas, doc: ScreenplayDocTemplate) -> None:
    meta = doc.title_meta
    center_lines: list[str] = meta.get("center_lines") or []
    footer_lines: list[str] = meta.get("footer_lines") or []

    canvas.saveState()
    canvas.setFont(FONT_REG, 12)
    cx = PAGE_SIZE[0] / 2
    line_gap = 14
    block_h = max(0, len(center_lines) - 1) * line_gap
    y = (PAGE_SIZE[1] + block_h) / 2
    for i, line in enumerate(center_lines):
        canvas.drawCentredString(cx, y - i * line_gap, line)
    canvas.setFont(FONT_REG, 12)
    fy = 3.5 * inch
    for line in footer_lines:
        canvas.drawString(1.0 * inch, fy, line)
        fy -= line_gap
    canvas.restoreState()


def _on_first_page(canvas, doc: ScreenplayDocTemplate) -> None:
    _draw_title_page(canvas, doc)


def _on_later_pages(canvas, doc: ScreenplayDocTemplate) -> None:
    _draw_page_number(canvas, doc)


def build_pdf(body: ExportBody) -> bytes:
    _ensure_fonts()
    title = _norm_text(body.title) or "Untitled"
    author = _norm_text(body.author)
    script_type = _norm_text(body.script_type)
    working_note = _norm_text(body.working_title_note)
    contact = _norm_text(body.contact_email)
    copyright_line = _norm_text(body.copyright_line)
    production = _norm_text(body.production_company)

    buf = io.BytesIO()
    doc = ScreenplayDocTemplate(
        buf,
        pagesize=PAGE_SIZE,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=title,
    )
    frame_w = PAGE_SIZE[0] - LEFT_MARGIN - RIGHT_MARGIN
    st = _styles(frame_w)

    center_lines: list[str] = []
    if script_type:
        center_lines.append(script_type.upper())
    center_lines.append(title.upper())
    if working_note:
        center_lines.append(working_note)
    center_lines.append("Written by")
    center_lines.append(author if author else " ")
    footer_lines = [x for x in (contact, copyright_line, production) if x]
    doc.title_meta = {"center_lines": center_lines, "footer_lines": footer_lines}

    story: list = []
    beat_flowables: list = []
    scene_num = 0
    prev_type: str | None = None
    blocks = body.blocks
    i = 0
    while i < len(blocks):
        block = blocks[i]
        btype = (block.type or "").strip().lower()
        if btype not in ALLOWED_TYPES:
            raise ValueError(f"Unknown block type: {block.type}")
        raw = block.text or ""
        if not raw.strip():
            i += 1
            continue

        if btype == "character":
            speech, next_i = _character_speech_group(blocks, i, st=st)
            if len(speech) > 1:
                beat_flowables.append(KeepTogether(speech))
            else:
                beat_flowables.extend(speech)
            prev_type = (blocks[next_i - 1].type or "").strip().lower()
            i = next_i
            continue

        if btype == "scene":
            group, next_i, scene_num = _scene_opening_group(
                blocks,
                i,
                scene_num=scene_num,
                prev_type=prev_type,
                st=st,
            )
            if next_i > i + 1:
                beat_flowables.append(KeepTogether(group))
            else:
                beat_flowables.extend(group)
            prev_type = (blocks[next_i - 1].type or "").strip().lower()
            i = next_i
            continue

        scene_num, prev_type = _append_block_flowables(
            beat_flowables,
            block,
            st=st,
            prev_type=prev_type,
            scene_num=scene_num,
        )
        i += 1

    if beat_flowables:
        doc.script_start_page = 2
        story.append(PageBreak())
        story.extend(beat_flowables)
    else:
        doc.script_start_page = None
        story.append(Spacer(1, 0.01))

    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)
    return buf.getvalue()
