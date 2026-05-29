#!/usr/bin/env python3
"""Capture README screenshots from a running ScriptBox server."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import fitz
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pdf_export import Block, ExportBody, build_pdf

BASE = "http://127.0.0.1:8765"
PROJECT = "readme-demo01"
OUT = ROOT / "docs" / "readme-assets"

DEMO_BLOCKS = [
    Block(type="scene", text="INT. COFFEE SHOP - NIGHT"),
    Block(type="action", text="Rain streaks the window. MAYA checks her phone. The door chimes."),
    Block(type="character", text="MAYA"),
    Block(type="dialogue", text="He's not coming."),
    Block(type="action", text="She slides the untouched latte away."),
    Block(type="scene", text="EXT. ALLEY - CONTINUOUS"),
    Block(type="action", text="MAYA bursts outside. A figure waits under a flickering sign."),
    Block(type="character", text="STRANGER"),
    Block(type="parenthetical", text="(quietly)"),
    Block(type="dialogue", text="Wrong door, Maya."),
    Block(type="transition", text="CUT TO:"),
]


def script_page_png_b64() -> str:
    pdf = build_pdf(
        ExportBody(title="The Midnight Run", author="Alex Writer", blocks=DEMO_BLOCKS),
    )
    doc = fitz.open(stream=pdf, filetype="pdf")
    page = doc.load_page(1)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    return base64.b64encode(pix.tobytes("png")).decode("ascii")


def inject_preview_image(page, b64: str) -> None:
    page.evaluate(
        """(b64) => {
          const wrap = document.querySelector('.preview-frame-wrap');
          const iframe = document.getElementById('pdfPreview');
          const ph = document.getElementById('previewPlaceholder');
          if (ph) ph.classList.add('hidden');
          if (iframe) iframe.style.display = 'none';
          let img = document.getElementById('readmePreviewImg');
          if (!img) {
            img = document.createElement('img');
            img.id = 'readmePreviewImg';
            img.alt = 'PDF preview';
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'contain';
            img.style.background = '#fff';
            wrap.appendChild(img);
          }
          img.src = 'data:image/png;base64,' + b64;
        }""",
        b64,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    preview_b64 = script_page_png_b64()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
        page.goto(f"{BASE}/edit?p={PROJECT}", wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(800)

        page.locator(".editor-pane").evaluate("el => { el.scrollTop = 200; }")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "beat-editor.png"))

        page.locator("#btnTogglePreview").click()
        page.wait_for_timeout(400)
        inject_preview_image(page, preview_b64)
        page.wait_for_timeout(300)
        page.locator(".preview-pane").screenshot(path=str(OUT / "pdf-preview.png"))
        page.screenshot(path=str(OUT / "editor-with-preview.png"))

        page.locator("#btnVersions").click()
        page.wait_for_selector("#versionsDialog[open]")
        page.wait_for_timeout(300)
        page.locator("#versionsDialog").screenshot(path=str(OUT / "saved-versions.png"))

        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        page.locator("#btnSaveVersion").click()
        page.wait_for_timeout(700)
        page.locator(".app-top").screenshot(path=str(OUT / "save-version-toolbar.png"))

        browser.close()

    for stale in (
        "script-editor.png",
        "new-project-filled.png",
        "_tmp_preview.pdf",
        "_tmp_preview.pdf.png",
        "pdf-script-page.png",
    ):
        p = OUT / stale
        if p.exists():
            p.unlink()

    print(f"Wrote screenshots to {OUT}")


if __name__ == "__main__":
    main()
