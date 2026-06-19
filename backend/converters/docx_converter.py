from pathlib import Path
from typing import AsyncIterator

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


async def convert(path: Path) -> AsyncIterator[dict]:
    try:
        doc = Document(str(path))
    except Exception as e:
        yield {
            "section": "Error",
            "markdown": f"> **Could not open this Word file** — it may be corrupt, password-protected, or not a valid .docx.\n>\n> `{e}`\n",
            "progress": 1.0,
        }
        return

    try:
        body_elements = list(iter_block_items(doc))
    except Exception as e:
        yield {
            "section": "Error",
            "markdown": f"> **Could not read document structure.**\n>\n> `{e}`\n",
            "progress": 1.0,
        }
        return

    total = max(len(body_elements), 1)
    buffer = []
    section_title = "Document"

    for i, item in enumerate(body_elements):
        try:
            if isinstance(item, Paragraph):
                md = paragraph_to_markdown(item)
                if md.startswith("#"):
                    if buffer:
                        yield {
                            "section": section_title,
                            "markdown": "\n\n".join(buffer) + "\n",
                            "progress": (i + 1) / total,
                        }
                        buffer = []
                    section_title = md.lstrip("#").strip() or section_title
                if md:
                    buffer.append(md)
            elif isinstance(item, Table):
                buffer.append(table_to_markdown(item))
        except Exception as e:
            # Skip the broken element, don't kill the whole document.
            buffer.append(f"<!-- skipped one element due to error: {e} -->")

    if buffer:
        yield {
            "section": section_title,
            "markdown": "\n\n".join(buffer) + "\n",
            "progress": 1.0,
        }


def iter_block_items(doc):
    """Yield paragraphs and tables in document order."""
    parent_elm = doc.element.body
    for child in parent_elm.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("}tbl"):
            yield Table(child, doc)


def paragraph_to_markdown(p: Paragraph) -> str:
    text = p.text.strip()
    if not text:
        return ""
    try:
        style = (p.style.name or "").lower()
    except Exception:
        style = ""
    if "heading 1" in style or "title" in style:
        return f"# {text}"
    if "heading 2" in style:
        return f"## {text}"
    if "heading 3" in style:
        return f"### {text}"
    if "heading" in style:
        return f"#### {text}"
    if "list" in style:
        return f"- {text}"
    return text


def table_to_markdown(table: Table) -> str:
    try:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    except Exception as e:
        return f"<!-- could not read table: {e} -->"

    if not rows:
        return ""

    # Guard against ragged rows (merged cells can make rows uneven lengths)
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    header = rows[0]
    sep = ["---"] * width
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows[1:]:
        # Escape pipe characters so they don't break the table grid
        safe_row = [cell.replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(safe_row) + " |")
    return "\n".join(lines)