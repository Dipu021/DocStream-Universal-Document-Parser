import io
import re
from pathlib import Path
from typing import AsyncIterator, Optional

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")
# A line that's just a clause marker like "1.", "(1)", "(a)" sitting alone,
# meant to be glued onto the text that follows it.
CLAUSE_MARKER_RE = re.compile(r"^(\(?[0-9]{1,3}\)?\.?|\([a-z]\))$", re.IGNORECASE)
SENTENCE_END_CHARS = (".", ":", ";", ")", "\u201d", '"')


class PageMerger:
    """
    Joins PDF text lines into real paragraphs, carrying an unfinished
    sentence/clause across page boundaries so a paragraph that wraps from
    page N to page N+1 doesn't get split in the output.
    """

    def __init__(self):
        self.buf = ""
        self.buf_started_with_marker = False

    def feed_page(self, text: str) -> str:
        """Feed one page's raw text in, get back the markdown for the
        completed blocks on this page (anything still unfinished carries
        over to the next call)."""
        if not text:
            return ""

        raw_lines = [l.strip() for l in text.split("\n")]
        raw_lines = [l for l in raw_lines if l]
        raw_lines = [l for l in raw_lines if not PAGE_NUMBER_RE.match(l)]

        merged = []

        for line in raw_lines:
            if CLAUSE_MARKER_RE.match(line):
                if self.buf:
                    merged.append(self.buf)
                self.buf = line + " "
                self.buf_started_with_marker = True
                continue

            if self.buf_started_with_marker:
                self.buf = (self.buf + " " + line).strip()
                self.buf_started_with_marker = False
                if self.buf.endswith(SENTENCE_END_CHARS):
                    merged.append(self.buf)
                    self.buf = ""
                continue

            if looks_like_heading(line):
                if self.buf:
                    merged.append(self.buf)
                    self.buf = ""
                merged.append(line)
                continue

            self.buf = (self.buf + " " + line).strip() if self.buf else line
            if self.buf.endswith(SENTENCE_END_CHARS):
                merged.append(self.buf)
                self.buf = ""

        # NOTE: self.buf is deliberately NOT flushed here — it carries over
        # to the next page so a wrapped paragraph stays intact. Call
        # flush() after the last page to emit whatever's left.

        return "\n\n".join(to_markdown_block(b) for b in merged)

    def flush(self) -> str:
        if self.buf:
            out = to_markdown_block(self.buf)
            self.buf = ""
            return out
        return ""


def looks_like_heading(line: str) -> bool:
    """Real structural headings in this kind of doc: 'Part-1', 'Schedule-1',
    or a short Title Case line with no trailing punctuation."""
    if re.match(r"^(part|schedule)\s*-?\s*\d+", line, re.IGNORECASE):
        return True
    if len(line) < 50 and not line.endswith((".", ",", ";", ":")) and line[0:1].isupper():
        words = line.split()
        if 1 <= len(words) <= 6:
            return True
    return False


def to_markdown_block(block: str) -> str:
    if re.match(r"^(part|schedule)\s*-?\s*\d+", block, re.IGNORECASE):
        return f"## {block}"
    if looks_like_heading(block) and len(block) < 50:
        return f"### {block}"
    return block


def ocr_page(page) -> Optional[str]:
    """Render a page to an image and OCR it. Returns None if OCR isn't
    available or fails, so callers can fall back gracefully."""
    try:
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img).strip()
        return text or None
    except Exception:
        return None


async def convert(path: Path) -> AsyncIterator[dict]:
    try:
        doc = fitz.open(str(path))
    except Exception as e:
        yield {
            "section": "Error",
            "markdown": f"> **Could not open PDF** — the file may be corrupt or password-protected.\n>\n> `{e}`\n",
            "progress": 1.0,
        }
        return

    total = max(len(doc), 1)
    merger = PageMerger()
    ocr_unavailable_warned = False

    for i, page in enumerate(doc):
        try:
            text = page.get_text("text").strip()
        except Exception as e:
            text = ""

        if len(text) < 20:
            ocr_text = ocr_page(page)
            if ocr_text:
                text = ocr_text
            elif not ocr_text and not text and not ocr_unavailable_warned:
                # Only warn once per document, not once per scanned page.
                text = "<!-- This page appears to be scanned/image-based and OCR did not return text (Tesseract may not be installed). -->"
                ocr_unavailable_warned = True

        try:
            md = merger.feed_page(text)
        except Exception as e:
            md = f"<!-- Formatting error on this page: {e} -->\n\n{text}"

        if md.strip():
            yield {
                "section": f"Page {i + 1}",
                "markdown": md,
                "progress": (i + 1) / total,
            }

    tail = merger.flush()
    if tail.strip():
        yield {
            "section": "Page (final)",
            "markdown": tail,
            "progress": 1.0,
        }

    doc.close()